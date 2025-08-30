"""
Transaction Parser Service
Enhanced with Merchant KB integration for improved accuracy
Implements parse_transaction with regex normalization, merchant KB lookup, and LLM fallback
"""

import re
import logging
from typing import Dict, Optional
from app.services.llm_client import llm_client
from app.models.pydantic_models import TransactionCategory

logger = logging.getLogger(__name__)

# Merchant dictionary for common merchant mappings
MERCHANT_DICTIONARY = {
    # E-commerce
    "AMZN": "Amazon",
    "AMAZON": "Amazon", 
    "FLIPKART": "Flipkart",
    "MYNTRA": "Myntra",
    "NYKAA": "Nykaa",

    # Food delivery
    "ZOMATO": "Zomato",
    "SWIGGY": "Swiggy",
    "UBER EATS": "Uber Eats",
    "DUNZO": "Dunzo",

    # Transportation
    "UBER": "Uber",
    "OLA": "Ola",
    "METRO": "Metro",
    "IRCTC": "IRCTC",

    # Utilities & Bills
    "AIRTEL": "Airtel",
    "JIO": "Jio",
    "VODAFONE": "Vodafone",
    "BSNL": "BSNL",
    "TATAPOWER": "Tata Power",
    "ADANI": "Adani Power",

    # Entertainment
    "NETFLIX": "Netflix",
    "PRIME": "Amazon Prime",
    "HOTSTAR": "Disney+ Hotstar",
    "SPOTIFY": "Spotify",
    "YOUTUBE": "YouTube Premium",

    # Banking & Finance
    "SBI": "State Bank of India",
    "HDFC": "HDFC Bank",
    "ICICI": "ICICI Bank",
    "AXIS": "Axis Bank",
    "KOTAK": "Kotak Bank",
    "PAYTM": "Paytm",
    "PHONEPE": "PhonePe",
    "GPAY": "Google Pay",

    # Retail & Grocery
    "DMart": "DMart",
    "BIGBASKET": "BigBasket",
    "GROFERS": "Blinkit",
    "RELIANCE": "Reliance",
    "SPENCER": "Spencer's"
}

# Category mapping for merchants
MERCHANT_CATEGORIES = {
    "Amazon": TransactionCategory.SHOPPING,
    "Flipkart": TransactionCategory.SHOPPING,
    "Myntra": TransactionCategory.SHOPPING,
    "Nykaa": TransactionCategory.SHOPPING,
    "Zomato": TransactionCategory.FOOD,
    "Swiggy": TransactionCategory.FOOD,
    "Uber Eats": TransactionCategory.FOOD,
    "Dunzo": TransactionCategory.FOOD,
    "Uber": TransactionCategory.TRANSPORT,
    "Ola": TransactionCategory.TRANSPORT,
    "Metro": TransactionCategory.TRANSPORT,
    "IRCTC": TransactionCategory.TRANSPORT,
    "Netflix": TransactionCategory.ENTERTAINMENT,
    "Amazon Prime": TransactionCategory.ENTERTAINMENT,
    "Disney+ Hotstar": TransactionCategory.ENTERTAINMENT,
    "Spotify": TransactionCategory.ENTERTAINMENT,
    "YouTube Premium": TransactionCategory.ENTERTAINMENT,
    "Airtel": TransactionCategory.BILLS,
    "Jio": TransactionCategory.BILLS,
    "Vodafone": TransactionCategory.BILLS,
    "BSNL": TransactionCategory.BILLS,
    "Tata Power": TransactionCategory.BILLS,
    "Adani Power": TransactionCategory.BILLS,
    "DMart": TransactionCategory.FOOD,
    "BigBasket": TransactionCategory.FOOD,
    "Blinkit": TransactionCategory.FOOD,
}

def _apply_regex_normalizers(raw_desc: str) -> str:
    """
    Apply deterministic regex normalizers to clean transaction description

    Args:
        raw_desc: Raw transaction description

    Returns:
        Cleaned transaction description
    """
    cleaned = raw_desc.strip()

    # Remove timestamps and dates
    cleaned = re.sub(r'\d{2}[/-]\d{2}[/-]\d{2,4}', '', cleaned)
    cleaned = re.sub(r'\d{2}:\d{2}:\d{2}', '', cleaned)

    # Normalize UPI prefixes (preserve merchant name)
    cleaned = re.sub(r'^UPI-([A-Z]+)\d+-', r'\1-', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^UPI/([A-Z]+)\d+/', r'\1/', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^UPI-', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^UPI/', '', cleaned, flags=re.IGNORECASE)

    # Normalize IMPS prefixes (preserve merchant name)
    cleaned = re.sub(r'^IMPS-([A-Z]+)\d+-', r'\1-', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^IMPS/([A-Z]+)\d+/', r'\1/', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^IMPS-', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^IMPS/', '', cleaned, flags=re.IGNORECASE)

    # Normalize NEFT/RTGS prefixes
    cleaned = re.sub(r'^NEFT-([A-Z]+)\d+-', r'\1-', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^RTGS-([A-Z]+)\d+-', r'\1-', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^NEFT-', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^RTGS-', '', cleaned, flags=re.IGNORECASE)

    # Remove transaction IDs (long numeric sequences after merchant names)
    cleaned = re.sub(r'\d{8,}', '', cleaned)

    # Remove common banking suffixes
    cleaned = re.sub(r'\s*-\s*\d+$', '', cleaned)
    cleaned = re.sub(r'\s*REF\s*\w+$', '', cleaned, flags=re.IGNORECASE)

    # Clean up extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned

def _lookup_merchant(cleaned_desc: str) -> Optional[str]:
    """
    Lookup merchant from dictionary using cleaned description

    Args:
        cleaned_desc: Cleaned transaction description

    Returns:
        Matched merchant name or None
    """
    desc_upper = cleaned_desc.upper()

    # Direct matches first
    for key, merchant in MERCHANT_DICTIONARY.items():
        if key in desc_upper:
            return merchant

    # Partial matches for compound merchant names
    for key, merchant in MERCHANT_DICTIONARY.items():
        if len(key) > 3 and any(word in desc_upper for word in key.split()):
            return merchant

    return None

async def parse_transaction(raw_desc: str) -> Dict[str, any]:
    """
    Enhanced parsing with Merchant KB integration for better accuracy

    Flow: Regex normalization -> Merchant KB -> Dictionary lookup -> LLM fallback

    Args:
        raw_desc: Raw transaction description from bank

    Returns:
        Dict with keys: {cleaned_desc, merchant_candidate, category_candidate, confidence, explanation}

    Unit test expectations:
    - parse_transaction("UPI-AMZN123456-Payment") -> {merchant: "Amazon", category: "shopping", confidence: 0.95}
    - parse_transaction("IMPS-ZOMATO789-Food Order") -> {merchant: "Zomato", category: "food", confidence: 0.95}
    - parse_transaction("Random Merchant XYZ") -> {merchant: None/LLM, category: "other", confidence: 0.0-0.8}
    """
    logger.debug(f"Parsing transaction: {raw_desc}")

    # Step 1: Apply regex normalizers
    cleaned_desc = _apply_regex_normalizers(raw_desc)

    # Step 2: Try enhanced LLM client (which includes Merchant KB + fallback)
    llm_result = await llm_client.classify_transaction(cleaned_desc)

    merchant_candidate = _lookup_merchant(cleaned_desc)
    category_candidate = None
    explanation = "No classification method succeeded"
    confidence = 0.0

    # Use LLM client result (which includes Merchant KB integration)
    if llm_result.get("merchant"):
        merchant_candidate = llm_result["merchant"]
        category_candidate = llm_result["category"]
        confidence = llm_result.get("confidence", 0.5)
        explanation = llm_result.get("explanation", "LLM classification")
        logger.debug(f"LLM/KB classification: {merchant_candidate} -> {category_candidate} (confidence: {confidence})")

    # Fallback to dictionary lookup if LLM/KB didn't find anything
    elif merchant_candidate:
        confidence = 0.8  # Medium confidence for dictionary matches
        category_candidate = MERCHANT_CATEGORIES.get(merchant_candidate, TransactionCategory.OTHER).value
        explanation = f"Dictionary match: {merchant_candidate}"
        logger.debug(f"Dictionary match: {merchant_candidate} -> {category_candidate}")
    else:
        # No matches found anywhere
        category_candidate = TransactionCategory.OTHER.value
        confidence = 0.0
        explanation = "No merchant patterns matched"
        logger.debug("No merchant classification found")

    return {
        "cleaned_desc": cleaned_desc,
        "merchant_candidate": merchant_candidate,
        "category_candidate": category_candidate,
        "confidence": confidence,
        "explanation": explanation
    }
#    - "UPI-AMZN12345678-Payment" -> "AMZN-Payment"  
#    - "IMPS/ZOMATO87654321/Food" -> "ZOMATO/Food"
#    - "NEFT-HDFC123456789-Transfer 12:34:56" -> "HDFC-Transfer"
#
# 2. test_merchant_lookup():
#    - "AMZN Shopping" -> "Amazon"
#    - "ZOMATO Food Order" -> "Zomato" 
#    - "Unknown Merchant" -> None
#
# 3. test_full_parsing():
#    - "UPI-AMZN12345-Shopping" -> {merchant: "Amazon", category: "shopping", confidence: 0.9}
#    - "IMPS-SWIGGY789-Delivery" -> {merchant: "Swiggy", category: "food", confidence: 0.9}
#    - "Cash Withdrawal ATM" -> {merchant: "ATM Withdrawal", category: "other", confidence: 0.3}
#
# 4. test_edge_cases():
#    - "" -> {merchant: None, category: "other", confidence: 0.3}
#    - "   " -> {merchant: None, category: "other", confidence: 0.3}
#    - "ZOMATO ZOMATO ZOMATO" -> {merchant: "Zomato", category: "food", confidence: 0.9}