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
from .merchant_kb_service import merchant_kb, MerchantMatch

logger = logging.getLogger(__name__)

# Configuration
USE_REMOTE_LLM = os.getenv("USE_REMOTE_LLM", "false").lower() == "true"
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://localhost:8080/v1/llm")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))

class LLMClient:
    """
    Enhanced LLM client with Merchant KB integration for transaction classification

    Priority: Merchant KB -> Fallback Keywords -> Remote LLM
    """

    def __init__(self):
        # Fallback keyword-based classification rules (used when Merchant KB fails)
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

        # Load merchant KB on initialization
        merchant_kb.load_kb()

    async def classify_transaction(self, text: str) -> Dict[str, Optional[str]]:
        """
        Classify transaction using Merchant KB, fallback keywords, or remote LLM

        Args:
            text: Transaction description text

        Returns:
            Dict with 'merchant', 'category', and 'explanation' keys
        """
        if USE_REMOTE_LLM:
            return await self._classify_with_hybrid_approach(text)
        else:
            return await self._classify_with_hybrid_approach(text)

    async def _classify_with_hybrid_approach(self, text: str) -> Dict[str, Optional[str]]:
        """
        Hybrid classification: Merchant KB -> Fallback Keywords -> LLM

        Args:
            text: Transaction description

        Returns:
            Classification result with explanation
        """
        # Step 1: Try Merchant KB first (highest priority)
        kb_match = merchant_kb.match_merchant(text)
        if kb_match and kb_match.confidence >= 0.7:  # High confidence threshold for KB
            return {
                "merchant": kb_match.merchant,
                "category": kb_match.category,
                "confidence": kb_match.confidence,
                "explanation": f"Merchant KB {kb_match.match_type} match: '{kb_match.pattern}' (confidence: {kb_match.confidence:.2f})"
            }

        # Step 2: Try fallback keywords
        fallback_result = await self._classify_with_heuristics(text)

        # Step 3: If we have a KB match with lower confidence, compare with fallback
        if kb_match:
            # If fallback found nothing, use KB match even with lower confidence
            if fallback_result.get("merchant") is None:
                return {
                    "merchant": kb_match.merchant,
                    "category": kb_match.category,
                    "confidence": kb_match.confidence,
                    "explanation": f"Merchant KB {kb_match.match_type} match (low confidence): '{kb_match.pattern}' (confidence: {kb_match.confidence:.2f})"
                }

            # If both found something, prefer KB if confidence is reasonably close
            if kb_match.confidence >= 0.5:
                return {
                    "merchant": kb_match.merchant,
                    "category": kb_match.category,
                    "confidence": kb_match.confidence,
                    "explanation": f"Merchant KB {kb_match.match_type} match over fallback: '{kb_match.pattern}' (confidence: {kb_match.confidence:.2f})"
                }

        # Step 4: Use fallback result or try LLM if enabled
        if USE_REMOTE_LLM and fallback_result.get("merchant") is None:
            try:
                llm_result = await self._call_llm_endpoint(text)
                llm_result["explanation"] = f"LLM classification (KB and fallback failed): {llm_result.get('explanation', '')}"
                return llm_result
            except Exception as e:
                logger.error(f"LLM classification failed: {e}")
                fallback_result["explanation"] = f"All methods failed, using fallback: {fallback_result.get('explanation', '')}"

        return fallback_result

    async def _classify_with_heuristics(self, text: str) -> Dict[str, Optional[str]]:
        """
        Fallback keyword-based classification (used when Merchant KB fails)

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
                "confidence": 0.0,
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
                "confidence": 0.8,  # Fixed confidence for fallback keywords
                "explanation": f"Keyword match: '{keyword}' in transaction description"
            }

        # No matches found
        return {
            "merchant": None,
            "category": TransactionCategory.OTHER.value,
            "confidence": 0.0,
            "explanation": f"No keyword matches found for: '{text[:50]}...'"
        }

    async def _classify_with_remote_llm(self, text: str) -> Dict[str, Optional[str]]:
        """
        Classify transaction using remote Llama-3 8B endpoint (deprecated, use hybrid approach)

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
            return result

    asyncio.run(test_llm_client())

    # Test merchant KB integration
    async def test_merchant_kb():
        """Test merchant KB integration"""
        print("\n🏪 Testing Merchant KB Integration\n")

        kb_test_cases = [
            "ZOMATO*ORDER12345",
            "AMZ*PURCHASE789", 
            "UBER*TRIP456",
            "NETFLIX SUBSCRIPTION",
            "AIRTEL BILL PAYMENT",
            "Unknown Merchant ABC"
        ]

        for desc in kb_test_cases:
            result = await llm_client.classify_transaction(desc)
            print(f"Input: '{desc}'")
            print(f"Merchant: {result.get('merchant')}")
            print(f"Category: {result.get('category')}")
            print(f"Confidence: {result.get('confidence', 'N/A')}")
            print(f"Explanation: {result.get('explanation')}")
            print()

    print("\n" + "="*50)
    asyncio.run(test_merchant_kb())