"""
LLM Client for transaction classification

Provides both deterministic heuristic classification for development and 
production-ready LLM integration with Llama-3 8B endpoint.

Features:
- Deterministic keyword-based classification for development
- Optional remote LLM integration behind USE_REMOTE_LLM flag
- Comprehensive merchant and category detection
- Confidence scoring and explanations
"""

import os
import logging
import httpx
import asyncio
from typing import Dict, Optional, Any
from app.models.pydantic_models import TransactionCategory

logger = logging.getLogger(__name__)

# Configuration
USE_REMOTE_LLM = os.getenv("USE_REMOTE_LLM", "false").lower() == "true"
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://localhost:8080/v1/llm")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))

class LLMClient:
    """
    Advanced LLM client for transaction classification

    Supports both deterministic heuristics (dev) and remote LLM calls (prod)
    """

    def __init__(self):
        # Comprehensive keyword-based classification rules
        self.merchant_keywords = {
            # E-commerce & Shopping
            "amazon": {"merchant": "Amazon", "category": TransactionCategory.SHOPPING},
            "flipkart": {"merchant": "Flipkart", "category": TransactionCategory.SHOPPING},
            "myntra": {"merchant": "Myntra", "category": TransactionCategory.SHOPPING},
            "nykaa": {"merchant": "Nykaa", "category": TransactionCategory.SHOPPING},
            "shopping": {"merchant": "Online Shopping", "category": TransactionCategory.SHOPPING},

            # Food & Dining
            "zomato": {"merchant": "Zomato", "category": TransactionCategory.FOOD},
            "swiggy": {"merchant": "Swiggy", "category": TransactionCategory.FOOD},
            "restaurant": {"merchant": "Restaurant", "category": TransactionCategory.FOOD},
            "food": {"merchant": "Food Purchase", "category": TransactionCategory.FOOD},
            "cafe": {"merchant": "Cafe", "category": TransactionCategory.FOOD},
            "pizza": {"merchant": "Pizza Order", "category": TransactionCategory.FOOD},
            "mcdonald": {"merchant": "McDonald's", "category": TransactionCategory.FOOD},
            "kfc": {"merchant": "KFC", "category": TransactionCategory.FOOD},
            "dominos": {"merchant": "Domino's", "category": TransactionCategory.FOOD},

            # Transportation
            "uber": {"merchant": "Uber", "category": TransactionCategory.TRANSPORT},
            "ola": {"merchant": "Ola", "category": TransactionCategory.TRANSPORT},
            "metro": {"merchant": "Metro", "category": TransactionCategory.TRANSPORT},
            "taxi": {"merchant": "Taxi", "category": TransactionCategory.TRANSPORT},
            "bus": {"merchant": "Bus", "category": TransactionCategory.TRANSPORT},
            "train": {"merchant": "Train", "category": TransactionCategory.TRANSPORT},
            "irctc": {"merchant": "IRCTC", "category": TransactionCategory.TRANSPORT},
            "airline": {"merchant": "Airline", "category": TransactionCategory.TRANSPORT},
            "flight": {"merchant": "Flight", "category": TransactionCategory.TRANSPORT},

            # Entertainment
            "netflix": {"merchant": "Netflix", "category": TransactionCategory.ENTERTAINMENT},
            "spotify": {"merchant": "Spotify", "category": TransactionCategory.ENTERTAINMENT},
            "youtube": {"merchant": "YouTube Premium", "category": TransactionCategory.ENTERTAINMENT},
            "prime": {"merchant": "Amazon Prime", "category": TransactionCategory.ENTERTAINMENT},
            "hotstar": {"merchant": "Disney+ Hotstar", "category": TransactionCategory.ENTERTAINMENT},
            "movie": {"merchant": "Movie Ticket", "category": TransactionCategory.ENTERTAINMENT},
            "cinema": {"merchant": "Cinema", "category": TransactionCategory.ENTERTAINMENT},
            "theater": {"merchant": "Theater", "category": TransactionCategory.ENTERTAINMENT},

            # Bills & Utilities
            "electricity": {"merchant": "Electricity Bill", "category": TransactionCategory.BILLS},
            "water": {"merchant": "Water Bill", "category": TransactionCategory.BILLS},
            "gas": {"merchant": "Gas Bill", "category": TransactionCategory.BILLS},
            "mobile": {"merchant": "Mobile Bill", "category": TransactionCategory.BILLS},
            "internet": {"merchant": "Internet Bill", "category": TransactionCategory.BILLS},
            "airtel": {"merchant": "Airtel", "category": TransactionCategory.BILLS},
            "jio": {"merchant": "Jio", "category": TransactionCategory.BILLS},
            "vodafone": {"merchant": "Vodafone", "category": TransactionCategory.BILLS},

            # Healthcare
            "pharmacy": {"merchant": "Pharmacy", "category": TransactionCategory.HEALTHCARE},
            "hospital": {"merchant": "Hospital", "category": TransactionCategory.HEALTHCARE},
            "doctor": {"merchant": "Doctor", "category": TransactionCategory.HEALTHCARE},
            "medical": {"merchant": "Medical", "category": TransactionCategory.HEALTHCARE},
            "health": {"merchant": "Healthcare", "category": TransactionCategory.HEALTHCARE},

            # Banking & Finance
            "atm": {"merchant": "ATM Withdrawal", "category": TransactionCategory.OTHER},
            "transfer": {"merchant": "Bank Transfer", "category": TransactionCategory.OTHER},
            "payment": {"merchant": "Online Payment", "category": TransactionCategory.OTHER},
            "card": {"merchant": "Card Payment", "category": TransactionCategory.OTHER},
            "loan": {"merchant": "Loan Payment", "category": TransactionCategory.OTHER},
            "insurance": {"merchant": "Insurance", "category": TransactionCategory.OTHER},

            # Income
            "salary": {"merchant": "Salary", "category": TransactionCategory.SALARY},
            "dividend": {"merchant": "Dividend", "category": TransactionCategory.INVESTMENT},
            "interest": {"merchant": "Interest", "category": TransactionCategory.INVESTMENT},
        }

    async def classify_transaction(self, text: str) -> Dict[str, Optional[str]]:
        """
        Classify transaction using deterministic heuristics or remote LLM

        Args:
            text: Transaction description text

        Returns:
            Dict with 'merchant', 'category', and 'explanation' keys
        """
        if USE_REMOTE_LLM:
            return await self._classify_with_remote_llm(text)
        else:
            return await self._classify_with_heuristics(text)

    async def _classify_with_heuristics(self, text: str) -> Dict[str, Optional[str]]:
        """
        Deterministic keyword-based classification for development

        Args:
            text: Transaction description

        Returns:
            Classification result with explanation
        """
        text_lower = text.lower().strip()

        # Handle empty or whitespace-only input
        if not text_lower:
            return {
                "merchant": None,
                "category": TransactionCategory.OTHER.value,
                "explanation": "Empty transaction description"
            }

        # Search for keyword matches (ordered by specificity)
        matched_keywords = []
        for keyword, info in self.merchant_keywords.items():
            if keyword in text_lower:
                matched_keywords.append((keyword, info))

        if matched_keywords:
            # Use the longest/most specific keyword match
            best_match = max(matched_keywords, key=lambda x: len(x[0]))
            keyword, info = best_match

            return {
                "merchant": info["merchant"],
                "category": info["category"].value,
                "explanation": f"Keyword match: '{keyword}' in transaction description"
            }

        # No matches found
        return {
            "merchant": None,
            "category": TransactionCategory.OTHER.value,
            "explanation": f"No keyword matches found for: '{text[:50]}...'"
        }

    async def _classify_with_remote_llm(self, text: str) -> Dict[str, Optional[str]]:
        """
        Classify transaction using remote Llama-3 8B endpoint

        Args:
            text: Transaction description

        Returns:
            LLM classification result
        """
        try:
            return await self._call_llm_endpoint(text)
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            # Fallback to heuristics on LLM failure
            logger.info("Falling back to heuristic classification")
            result = await self._classify_with_heuristics(text)
            result["explanation"] = f"LLM failed ({str(e)}), used heuristics: {result['explanation']}"
            return result

    async def _call_llm_endpoint(self, text: str) -> Dict[str, Any]:
        """
        Call remote Llama-3 8B endpoint for transaction classification

        TODO: Replace with actual LLM integration
        Expected API:
        - POST /v1/llm
        - Request: {"prompt": "...", "max_tokens": 150, "temperature": 0.1}
        - Response: {"response": "JSON formatted classification"}

        Args:
            text: Transaction description

        Returns:
            LLM response parsed as classification
        """
        prompt = self._build_classification_prompt(text)

        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            response = await client.post(
                LLM_ENDPOINT,
                json={
                    "prompt": prompt,
                    "max_tokens": 150,
                    "temperature": 0.1,
                    "stop": ["}", "\n\n"]
                },
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            llm_response = response.json()
            return self._parse_llm_response(llm_response.get("response", ""))

    def _build_classification_prompt(self, text: str) -> str:
        """Build prompt for LLM classification"""
        categories = [cat.value for cat in TransactionCategory]

        return f"""Classify this bank transaction into merchant name and category.

Transaction: "{text}"

Available categories: {', '.join(categories)}

Respond in JSON format:
{{
    "merchant": "merchant name or null",
    "category": "category from list",
    "explanation": "brief reasoning"
}}

Response:"""

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured format"""
        try:
            import json
            # Try to extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                parsed = json.loads(json_str)

                return {
                    "merchant": parsed.get("merchant"),
                    "category": parsed.get("category", TransactionCategory.OTHER.value),
                    "explanation": parsed.get("explanation", "LLM classification")
                }
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")

        # Fallback if parsing fails
        return {
            "merchant": None,
            "category": TransactionCategory.OTHER.value,
            "explanation": f"LLM response parsing failed: {response[:100]}..."
        }

# Global LLM client instance
llm_client = LLMClient()

# Example usage and testing
if __name__ == "__main__":
    async def test_llm_client():
        """Test the LLM client functionality"""
        test_cases = [
            "AMAZON Order 12345",
            "ZOMATO Food Delivery",
            "Netflix Subscription",
            "ATM Withdrawal",
            "Unknown Merchant XYZ"
        ]

        print("🧪 Testing LLM Client Classification\n")

        for desc in test_cases:
            result = await llm_client.classify_transaction(desc)
            print(f"Input: '{desc}'")
            print(f"Result: {result}")
            print()

    asyncio.run(test_llm_client())