"""
Test file to validate parse_transaction functionality
Run with: python -m pytest test_parser.py -v
"""

import asyncio
import pytest
from app.services.parser import parse_transaction, _apply_regex_normalizers, _lookup_merchant


class TestRegexNormalizers:
    """Test regex normalization functionality"""

    def test_remove_transaction_ids(self):
        """Test removal of transaction IDs"""
        assert _apply_regex_normalizers("UPI-AMZN12345678-Payment") == "UPI-AMZN-Payment"
        assert _apply_regex_normalizers("IMPS/ZOMATO87654321/Food") == "IMPS/ZOMATO/Food"

    def test_normalize_upi_prefixes(self):
        """Test UPI prefix normalization"""
        assert _apply_regex_normalizers("UPI-AMAZON Payment") == "AMAZON Payment"
        assert _apply_regex_normalizers("UPI/ZOMATO Food") == "ZOMATO Food"
        assert _apply_regex_normalizers("UPI SWIGGY Order") == "SWIGGY Order"

    def test_normalize_imps_prefixes(self):
        """Test IMPS prefix normalization"""
        assert _apply_regex_normalizers("IMPS-NETFLIX Subscription") == "NETFLIX Subscription"
        assert _apply_regex_normalizers("IMPS/UBER Ride") == "UBER Ride"

    def test_remove_timestamps(self):
        """Test timestamp removal"""
        assert _apply_regex_normalizers("HDFC Transfer 12:34:56") == "HDFC Transfer"
        assert _apply_regex_normalizers("Payment 01/02/2024") == "Payment"

    def test_whitespace_cleanup(self):
        """Test extra whitespace cleanup"""
        assert _apply_regex_normalizers("  AMAZON   Payment  ") == "AMAZON Payment"


class TestMerchantLookup:
    """Test merchant dictionary lookup"""

    def test_direct_matches(self):
        """Test direct merchant matches"""
        assert _lookup_merchant("AMZN Shopping") == "Amazon"
        assert _lookup_merchant("ZOMATO Food Order") == "Zomato"
        assert _lookup_merchant("NETFLIX Subscription") == "Netflix"

    def test_case_insensitive(self):
        """Test case insensitive matching"""
        assert _lookup_merchant("amzn shopping") == "Amazon"
        assert _lookup_merchant("zomato food") == "Zomato"

    def test_no_match(self):
        """Test when no merchant is found"""
        assert _lookup_merchant("Unknown Merchant XYZ") is None
        assert _lookup_merchant("Random Shop") is None


class TestFullParsing:
    """Test complete parse_transaction functionality"""

    @pytest.mark.asyncio
    async def test_high_confidence_parsing(self):
        """Test parsing with high confidence dictionary matches"""
        result = await parse_transaction("UPI-AMZN12345678-Shopping")
        assert result["merchant_candidate"] == "Amazon"
        assert result["category_candidate"] == "shopping"
        assert result["confidence"] == 0.9
        assert "AMZN-Shopping" in result["cleaned_desc"]

    @pytest.mark.asyncio
    async def test_food_category_parsing(self):
        """Test food category parsing"""
        result = await parse_transaction("IMPS-SWIGGY87654321-Delivery")
        assert result["merchant_candidate"] == "Swiggy"
        assert result["category_candidate"] == "food"
        assert result["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_llm_fallback(self):
        """Test LLM fallback for unknown merchants"""
        result = await parse_transaction("Random Unknown Merchant Payment")
        assert result["confidence"] == 0.3  # Lower confidence for LLM
        assert result["category_candidate"] == "other"
        assert result["cleaned_desc"] == "Random Unknown Merchant Payment"


if __name__ == "__main__":
    # Simple test runner for development
    async def run_tests():
        print("Testing parse_transaction functionality...")

        # Test high confidence case
        result1 = await parse_transaction("UPI-AMZN12345678-Shopping")
        print(f"Amazon test: {result1}")

        # Test food delivery
        result2 = await parse_transaction("IMPS-ZOMATO87654321-Food Order")  
        print(f"Zomato test: {result2}")

        # Test unknown merchant
        result3 = await parse_transaction("Some Random Merchant XYZ")
        print(f"Unknown merchant test: {result3}")

        print("All tests completed!")

    asyncio.run(run_tests())