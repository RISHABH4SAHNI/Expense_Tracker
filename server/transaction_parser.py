"""
Transaction Parser Microservice

A focused REST API service for parsing messy bank transaction descriptions.
Extracts merchant names, transaction types, and normalizes data for further processing.

Example usage:
    POST /parse
    {
        "raw_text": "NEFT-AXIS BANK-1234-UPI-FOODPANDA",
        "amount": 450.50,
        "date": "2024-01-15T10:30:00Z"
    }

    Response:
    {
        "merchant": "FoodPanda",
        "amount": 450.50,
        "date": "2024-01-15T10:30:00Z",
        "raw_text": "NEFT-AXIS BANK-1234-UPI-FOODPANDA",
        "transaction_type": "UPI",
        "confidence": 0.85,
        "cleaned_description": "FOODPANDA"
    }
"""

import re
import logging
import os
import httpx
import json as json_lib
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional, List
from enum import Enum

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, validator
import uvicorn
from app.models.pydantic_models import TransactionCategory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enums
class TransactionTypeEnum(str, Enum):
    """Detected transaction types"""
    UPI = "UPI"
    NEFT = "NEFT"
    RTGS = "RTGS"
    IMPS = "IMPS"
    ATM = "ATM"
    POS = "POS"
    NET_BANKING = "NET_BANKING"
    DEBIT_CARD = "DEBIT_CARD"
    CREDIT_CARD = "CREDIT_CARD"
    CASH = "CASH"
    OTHER = "OTHER"

# Pydantic Models
class ParseRequest(BaseModel):
    """Request model for transaction parsing"""
    raw_text: str = Field(..., min_length=1, max_length=500, description="Raw transaction description")
    amount: Optional[Decimal] = Field(None, ge=0, description="Transaction amount (optional)")
    date: Optional[datetime] = Field(None, description="Transaction date (optional)")

    @validator('raw_text')
    def validate_raw_text(cls, v):
        if not v or v.strip() == "":
            raise ValueError("raw_text cannot be empty")
        return v.strip()

class ParseResponse(BaseModel):
    """Response model for parsed transaction"""
    merchant: Optional[str] = Field(None, description="Extract merchant name")
    category: Optional[str] = Field(None, description="Transaction category")
    amount: Optional[Decimal] = Field(None, description="Transaction amount")
    date: Optional[datetime] = Field(None, description="Transaction date")
    raw_text: str = Field(..., description="Original raw transaction text")
    transaction_type: TransactionTypeEnum = Field(..., description="Detected transaction type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Parsing confidence score")
    cleaned_description: str = Field(..., description="Cleaned transaction description")
    parsing_method: str = Field(..., description="Method used for parsing (regex/dictionary/llm)")
    llm_used: bool = Field(False, description="Whether LLM was used for parsing")

# Enhanced Merchant Dictionary
MERCHANT_PATTERNS = {
    # E-commerce
    r'AMZN|AMAZON': "Amazon",
    r'FLIPKART': "Flipkart", 
    r'MYNTRA': "Myntra",
    r'NYKAA': "Nykaa",
    r'MEESHO': "Meesho",
    r'AJIO': "Ajio",

    # Food delivery
    r'ZOMATO': "Zomato",
    r'SWIGGY': "Swiggy", 
    r'UBEREATS|UBER\s*EATS': "Uber Eats",
    r'FOODPANDA': "FoodPanda",
    r'DUNZO': "Dunzo",
    r'DOMINOSPIZZA|DOMINOS': "Domino's Pizza",
    r'PIZZAHUT': "Pizza Hut",
    r'MCDONALD|MCDONALDS': "McDonald's",
    r'KFC': "KFC",

    # Transportation
    r'UBER(?!\s*EATS)': "Uber",
    r'OLA(?!\s*CABS)': "Ola",
    r'OLACABS': "Ola",
    r'METRO': "Metro",
    r'IRCTC': "IRCTC",
    r'RAPIDO': "Rapido",
    r'GOIBIBO': "Goibibo",
    r'MAKEMYTRIP': "MakeMyTrip",

    # Utilities & Bills
    r'AIRTEL': "Airtel",
    r'JIO|RELIANCE\s*JIO': "Jio",
    r'VODAFONE|VI': "Vodafone Idea",
    r'BSNL': "BSNL",
    r'TATAPOWER': "Tata Power",
    r'ADANI(?:\s*POWER)?': "Adani Power",
    r'BESCOM': "BESCOM",
    r'MSEB': "MSEB",

    # Entertainment & Subscriptions
    r'NETFLIX': "Netflix",
    r'PRIME(?:\s*VIDEO)?': "Amazon Prime",
    r'HOTSTAR|DISNEY': "Disney+ Hotstar",
    r'SPOTIFY': "Spotify",
    r'YOUTUBE(?:\s*PREMIUM)?': "YouTube Premium",
    r'SONY\s*LIV': "SonyLIV",
    r'ZEE5': "ZEE5",

    # Banking & Finance
    r'PAYTM': "Paytm",
    r'PHONEPE|PHONE\s*PE': "PhonePe",
    r'GPAY|GOOGLE\s*PAY': "Google Pay",
    r'MOBIKWIK': "MobiKwik",
    r'FREECHARGE': "FreeCharge",

    # Retail & Grocery
    r'DMART|D\s*MART': "DMart",
    r'BIGBASKET': "BigBasket",
    r'GROFERS|BLINKIT': "Blinkit",
    r'RELIANCE(?:\s*FRESH|\s*SMART)?': "Reliance",
    r'SPENCER': "Spencer's",
    r'MORE': "MORE",
    r'EASYDAY': "EasyDay",
}

# Category mapping for merchants (enhanced)
MERCHANT_CATEGORIES = {
    "Amazon": "shopping", "Flipkart": "shopping", "Myntra": "shopping", "Nykaa": "shopping",
    "Zomato": "food", "Swiggy": "food", "Uber Eats": "food", "FoodPanda": "food", "Dunzo": "food",
    "Uber": "transport", "Ola": "transport", "Metro": "transport", "IRCTC": "transport",
    "Netflix": "entertainment", "Amazon Prime": "entertainment", "Disney+ Hotstar": "entertainment",
    "Spotify": "entertainment", "YouTube Premium": "entertainment",
    "Airtel": "bills", "Jio": "bills", "Vodafone Idea": "bills", "BSNL": "bills",
    "Tata Power": "bills", "Adani Power": "bills",
    "DMart": "food", "BigBasket": "food", "Blinkit": "food",
    "Paytm": "other", "PhonePe": "other", "Google Pay": "other",
}

# LLM Configuration
USE_LLM_FALLBACK = os.getenv("USE_LLM_FALLBACK", "true").lower() == "true"
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://localhost:8080/v1/llm")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "10"))

class TransactionParser:
    """Core transaction parsing logic"""

    def __init__(self):
        self.compiled_patterns = {
            re.compile(pattern, re.IGNORECASE): merchant 
            for pattern, merchant in MERCHANT_PATTERNS.items()
        }

    def detect_transaction_type(self, raw_text: str) -> TransactionTypeEnum:
        """Detect transaction type from raw text"""
        text_upper = raw_text.upper()

        # Check prefixes first (most specific) - these indicate the actual transaction method
        if re.search(r'^NEFT\b', text_upper):
            return TransactionTypeEnum.NEFT
        elif re.search(r'^IMPS\b', text_upper):
            return TransactionTypeEnum.IMPS
        elif re.search(r'^UPI\b', text_upper):
            return TransactionTypeEnum.UPI
        elif re.search(r'^RTGS\b', text_upper):
            return TransactionTypeEnum.RTGS
        # Then check for patterns anywhere in text
        elif re.search(r'\bNEFT\b', text_upper):
            return TransactionTypeEnum.NEFT
        elif re.search(r'\bUPI\b', text_upper):
            return TransactionTypeEnum.UPI
        elif re.search(r'\bIMPS\b', text_upper):
            return TransactionTypeEnum.IMPS
        elif re.search(r'\bATM\b', text_upper):
            return TransactionTypeEnum.ATM
        elif re.search(r'\bPOS\b', text_upper):
            return TransactionTypeEnum.POS
        elif re.search(r'NET\s*BANKING|NETBANKING', text_upper):
            return TransactionTypeEnum.NET_BANKING
        elif re.search(r'DEBIT\s*CARD', text_upper):
            return TransactionTypeEnum.DEBIT_CARD
        elif re.search(r'CREDIT\s*CARD', text_upper):
            return TransactionTypeEnum.CREDIT_CARD
        elif re.search(r'\bCASH\b', text_upper):
            return TransactionTypeEnum.CASH
        else:
            return TransactionTypeEnum.OTHER

    def clean_description(self, raw_text: str) -> str:
        """Apply regex normalizers to clean transaction description"""
        cleaned = raw_text.strip()

        # Remove timestamps and dates
        cleaned = re.sub(r'\d{2}[/-]\d{2}[/-]\d{2,4}', '', cleaned)
        cleaned = re.sub(r'\d{2}:\d{2}:\d{2}', '', cleaned)

        # Remove transaction type prefixes while preserving merchant info
        cleaned = re.sub(r'^(UPI|NEFT|RTGS|IMPS|ATM|POS)[/-]?', '', cleaned, flags=re.IGNORECASE)

        # Remove bank names and transaction IDs
        bank_patterns = [
            r'HDFC\s*BANK?[/-]?\d*[/-]?',
            r'ICICI\s*BANK?[/-]?\d*[/-]?', 
            r'SBI\s*BANK?[/-]?\d*[/-]?',
            r'AXIS\s*BANK?[/-]?\d*[/-]?',
            r'KOTAK\s*BANK?[/-]?\d*[/-]?',
        ]
        for pattern in bank_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Remove long numeric sequences (transaction IDs)
        cleaned = re.sub(r'\b\d{8,}\b', '', cleaned)

        # Remove common suffixes
        cleaned = re.sub(r'\s*-\s*\d+$', '', cleaned)
        cleaned = re.sub(r'\s*REF\s*\w*$', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*TXN\s*\w*$', '', cleaned, flags=re.IGNORECASE)

        # Clean up extra whitespace and separators
        cleaned = re.sub(r'[/-]+', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned

    def extract_merchant(self, cleaned_text: str) -> Optional[str]:
        """Extract merchant name from cleaned text"""
        for pattern, merchant in self.compiled_patterns.items():
            if pattern.search(cleaned_text):
                return merchant
        return None

    def is_ambiguous_or_messy(self, raw_text: str, cleaned_text: str, merchant: Optional[str]) -> bool:
        """
        Determine if the transaction text is too messy or ambiguous for regex parsing

        Args:
            raw_text: Original transaction text
            cleaned_text: Cleaned transaction text
            merchant: Merchant found by regex (if any)

        Returns:
            True if LLM should be used as fallback
        """
        # Criteria for using LLM fallback
        criteria = {
            'no_merchant_found': merchant is None,
            'very_short_after_cleaning': len(cleaned_text.strip()) < 5,
            'mostly_numbers': len(re.findall(r'\d', cleaned_text)) > len(cleaned_text) * 0.7,
            'has_unusual_patterns': bool(re.search(r'[^a-zA-Z0-9\s\-/]', cleaned_text)),
            'multiple_merchants': len([p for p in self.compiled_patterns if p.search(cleaned_text)]) > 1,
            'low_alpha_ratio': len(re.findall(r'[a-zA-Z]', cleaned_text)) < len(cleaned_text) * 0.3,
            'has_typos_or_abbrev': bool(re.search(r'\b[A-Z]{2,}[0-9]+|[A-Z]+\*[A-Z]+\b', raw_text)),
        }

        # Use LLM if multiple criteria are met
        true_criteria = sum(criteria.values())
        ambiguity_score = true_criteria / len(criteria)

        logger.debug(f"Ambiguity analysis for '{raw_text[:50]}...': {criteria}, score: {ambiguity_score:.2f}")

        # Use LLM if ambiguity score > 0.4 (adjustable threshold)
        return ambiguity_score > 0.4

    async def call_llm_fallback(self, raw_text: str, cleaned_text: str) -> Dict[str, any]:
        """
        Call LLM for complex transaction parsing

        Args:
            raw_text: Original transaction text
            cleaned_text: Cleaned transaction text

        Returns:
            Dict with merchant, category, confidence, and explanation
        """
        try:
            prompt = self._build_llm_prompt(raw_text, cleaned_text)

            async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
                response = await client.post(
                    LLM_ENDPOINT,
                    json={
                        "prompt": prompt,
                        "max_tokens": 200,
                        "temperature": 0.2,
                        "stop": ["}"]
                    },
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    llm_response = response.json().get("response", "")
                    return self._parse_llm_response(llm_response)
                else:
                    logger.warning(f"LLM endpoint returned {response.status_code}")

        except Exception as e:
            logger.error(f"LLM fallback failed: {e}")

        # Fallback to basic classification if LLM fails
        return {
            "merchant": None,
            "category": "other",
            "confidence": 0.2,
            "explanation": "LLM fallback failed, using default classification"
        }

    def _build_llm_prompt(self, raw_text: str, cleaned_text: str) -> str:
        """Build optimized prompt for LLM transaction classification"""
        categories = ["food", "transport", "shopping", "entertainment", "bills", "healthcare", "education", "salary", "investment", "other"]

        return f"""Analyze this bank transaction and extract the merchant name and category.

Original: "{raw_text}"
Cleaned: "{cleaned_text}"

Available categories: {', '.join(categories)}

Rules:
- If no clear merchant is identifiable, set merchant to null
- Choose the most appropriate category from the list
- Provide confidence between 0.0-1.0

Respond in JSON format:
{{
    "merchant": "merchant name or null",
    "category": "category from list",
    "confidence": 0.8,
    "explanation": "brief reasoning"
}}"""

    def _parse_llm_response(self, response: str) -> Dict[str, any]:
        """Parse LLM JSON response into structured format"""
        try:
            # Extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                parsed = json_lib.loads(json_str)

                return {
                    "merchant": parsed.get("merchant"),
                    "category": parsed.get("category", "other"),
                    "confidence": min(max(float(parsed.get("confidence", 0.5)), 0.0), 1.0),
                    "explanation": parsed.get("explanation", "LLM classification")
                }
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")

        # Fallback parsing
        return {
            "merchant": None,
            "category": "other", 
            "confidence": 0.3,
            "explanation": f"LLM response parsing failed"
        }

    async def parse(self, raw_text: str, amount: Optional[Decimal] = None, 
              date: Optional[datetime] = None) -> ParseResponse:
        """Enhanced parsing function with LLM fallback for complex cases"""

        # Step 1: Detect transaction type
        transaction_type = self.detect_transaction_type(raw_text)

        # Step 2: Clean description
        cleaned_description = self.clean_description(raw_text)

        # Step 3: Extract merchant
        merchant = self.extract_merchant(cleaned_description)
        category = MERCHANT_CATEGORIES.get(merchant, "other") if merchant else "other"

        # Step 4: Check if we need LLM fallback
        use_llm = False
        if USE_LLM_FALLBACK and self.is_ambiguous_or_messy(raw_text, cleaned_description, merchant):
            logger.info(f"Using LLM fallback for complex transaction: {raw_text[:50]}...")
            llm_result = await self.call_llm_fallback(raw_text, cleaned_description)

            # Use LLM result if it has higher confidence or found a merchant when regex didn't
            if (llm_result["confidence"] > 0.6 or 
                (merchant is None and llm_result["merchant"] is not None)):
                merchant = llm_result["merchant"]
                category = llm_result["category"]
                confidence = llm_result["confidence"]
                parsing_method = "llm_fallback"
                use_llm = True
                explanation = llm_result["explanation"]
            else:
                # LLM didn't provide better results, stick with regex
                confidence, parsing_method = self._calculate_regex_confidence(merchant, transaction_type)
                explanation = f"LLM attempted but regex preferred (LLM confidence: {llm_result['confidence']:.2f})"
        else:
            # Standard regex/dictionary parsing
            confidence, parsing_method = self._calculate_regex_confidence(merchant, transaction_type)
            explanation = f"Regex/dictionary parsing: {parsing_method}"

        return ParseResponse(
            merchant=merchant,
            category=category,
            amount=amount,
            date=date,
            raw_text=raw_text,
            transaction_type=transaction_type,
            confidence=confidence,
            cleaned_description=cleaned_description,
            parsing_method=parsing_method,
            llm_used=use_llm
        )

    def _calculate_regex_confidence(self, merchant: Optional[str], transaction_type: TransactionTypeEnum) -> tuple:
        """Calculate confidence and parsing method for regex-based results"""
        if merchant and transaction_type != TransactionTypeEnum.OTHER:
            return 0.85, "regex_dictionary"
        elif merchant:
            return 0.70, "dictionary_only"
        elif transaction_type != TransactionTypeEnum.OTHER:
            return 0.50, "transaction_type_only"
        else:
            return 0.30, "basic_cleaning"

# Initialize parser
parser = TransactionParser()

# FastAPI app
app = FastAPI(
    title="Transaction Parser Microservice",
    description="Parse messy bank transaction descriptions to extract merchant names and transaction types",
    version="1.0.0"
)

@app.post("/parse", response_model=ParseResponse)
async def parse_transaction(request: ParseRequest) -> ParseResponse:
    """
    Enhanced parsing with LLM fallback for complex cases

    Processes messy bank descriptions like:
    - "NEFT-AXIS BANK-1234-UPI-FOODPANDA" → merchant: "FoodPanda", category: "food"
    - "UPI-AMZN12345678-Shopping" → merchant: "Amazon", category: "shopping"
    - "ATM WDL HDFC BANK" → merchant: None, type: "ATM"
    """
    try:
        logger.info(f"Parsing transaction: {request.raw_text}")
        result = parser.parse(request.raw_text, request.amount, request.date)
        logger.info(f"Parse result: merchant={result.merchant}, type={result.transaction_type}, confidence={result.confidence}")
        return result
    except Exception as e:
        logger.error(f"Error parsing transaction: {e}")
        raise HTTPException(status_code=500, detail=f"Parsing error: {str(e)}")

@app.post("/parse/batch", response_model=List[ParseResponse])
async def parse_transactions_batch(requests: List[ParseRequest]) -> List[ParseResponse]:
    """Parse multiple transactions in a single request"""
    if len(requests) > 100:
        raise HTTPException(status_code=400, detail="Batch size cannot exceed 100 transactions")

    results = []
    for request in requests:
        try:
            result = await parser.parse(request.raw_text, request.amount, request.date)
            results.append(result)
        except Exception as e:
            logger.error(f"Error parsing transaction {request.raw_text}: {e}")
            # Add error result instead of failing entire batch
            results.append(ParseResponse(
                merchant=None,
                amount=request.amount,
                date=request.date,
                raw_text=request.raw_text,
                transaction_type=TransactionTypeEnum.OTHER,
                confidence=0.0,
                cleaned_description=request.raw_text,
                parsing_method="error",
                llm_used=False
            ))

    return results

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "transaction-parser",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)