"""
Test suite for Transaction Parser Microservice

Run with: 
    python -m pytest test_transaction_parser.py -v
    python test_transaction_parser.py  # For direct execution
"""

import pytest
import asyncio
from datetime import datetime
from decimal import Decimal
from fastapi.testclient import TestClient

from transaction_parser import app, parser, TransactionTypeEnum

# Test client
client = TestClient(app)

class TestTransactionTypeDetection:
    """Test transaction type detection functionality"""

    def test_upi_detection(self):
        """Test UPI transaction detection"""
        assert parser.detect_transaction_type("UPI-AMZN12345-Payment") == TransactionTypeEnum.UPI
        assert parser.detect_transaction_type("upi/merchant/payment") == TransactionTypeEnum.UPI
        assert parser.detect_transaction_type("Payment via UPI") == TransactionTypeEnum.UPI

    def test_neft_detection(self):
        """Test NEFT transaction detection"""
        assert parser.detect_transaction_type("NEFT-AXIS BANK-1234-Transfer") == TransactionTypeEnum.NEFT
        assert parser.detect_transaction_type("neft transfer") == TransactionTypeEnum.NEFT

    def test_imps_detection(self):
        """Test IMPS transaction detection"""
        assert parser.detect_transaction_type("IMPS-HDFC-5678-Quick Transfer") == TransactionTypeEnum.IMPS
        assert parser.detect_transaction_type("imps payment") == TransactionTypeEnum.IMPS

    def test_atm_detection(self):
        """Test ATM transaction detection"""
        assert parser.detect_transaction_type("ATM WDL HDFC BANK") == TransactionTypeEnum.ATM
        assert parser.detect_transaction_type("atm withdrawal") == TransactionTypeEnum.ATM

    def test_pos_detection(self):
        """Test POS transaction detection"""
        assert parser.detect_transaction_type("POS PURCHASE MERCHANT") == TransactionTypeEnum.POS
        assert parser.detect_transaction_type("pos terminal payment") == TransactionTypeEnum.POS

    def test_other_detection(self):
        """Test OTHER transaction detection for unknown types"""
        assert parser.detect_transaction_type("Some random payment") == TransactionTypeEnum.OTHER
        assert parser.detect_transaction_type("Cash payment") == TransactionTypeEnum.CASH

class TestDescriptionCleaning:
    """Test transaction description cleaning"""

    def test_remove_transaction_prefixes(self):
        """Test removal of transaction type prefixes"""
        assert parser.clean_description("UPI-AMZN12345678-Payment") == "AMZN Payment"
        assert parser.clean_description("NEFT-AXIS BANK-1234-FOODPANDA") == "FOODPANDA"
        assert parser.clean_description("IMPS/ZOMATO87654321/Food") == "ZOMATO Food"

    def test_remove_bank_names(self):
        """Test removal of bank names and IDs"""
        assert parser.clean_description("HDFC BANK-123-NETFLIX") == "NETFLIX"
        assert parser.clean_description("SBI-456-AMAZON PAYMENT") == "AMAZON PAYMENT"

    def test_remove_transaction_ids(self):
        """Test removal of long transaction IDs"""
        assert parser.clean_description("MERCHANT-123456789-Payment") == "MERCHANT Payment"
        assert parser.clean_description("AMAZON12345678Purchase") == "AMAZONPurchase"

    def test_remove_timestamps(self):
        """Test removal of timestamps and dates"""
        assert parser.clean_description("NETFLIX 12:34:56") == "NETFLIX"
        assert parser.clean_description("PAYMENT 01/02/2024") == "PAYMENT"
        assert parser.clean_description("TRANSFER 15-03-24") == "TRANSFER"

    def test_whitespace_normalization(self):
        """Test whitespace and separator normalization"""
        assert parser.clean_description("  AMAZON   PAYMENT  ") == "AMAZON PAYMENT"
        assert parser.clean_description("ZOMATO//FOOD") == "ZOMATO FOOD"
        assert parser.clean_description("UBER---RIDE") == "UBER RIDE"

class TestMerchantExtraction:
    """Test merchant name extraction"""

    def test_ecommerce_merchants(self):
        """Test e-commerce merchant extraction"""
        assert parser.extract_merchant("AMZN Shopping") == "Amazon"
        assert parser.extract_merchant("AMAZON PAYMENT") == "Amazon"
        assert parser.extract_merchant("FLIPKART ORDER") == "Flipkart"
        assert parser.extract_merchant("MYNTRA FASHION") == "Myntra"

    def test_food_delivery_merchants(self):
        """Test food delivery merchant extraction"""
        assert parser.extract_merchant("ZOMATO FOOD ORDER") == "Zomato"
        assert parser.extract_merchant("SWIGGY DELIVERY") == "Swiggy"
        assert parser.extract_merchant("FOODPANDA ORDER") == "FoodPanda"
        assert parser.extract_merchant("UBER EATS DELIVERY") == "Uber Eats"

    def test_transportation_merchants(self):
        """Test transportation merchant extraction"""
        assert parser.extract_merchant("UBER RIDE") == "Uber"
        assert parser.extract_merchant("OLA CAB BOOKING") == "Ola"
        assert parser.extract_merchant("METRO TRAVEL") == "Metro"
        assert parser.extract_merchant("IRCTC TICKET") == "IRCTC"

    def test_utilities_merchants(self):
        """Test utilities merchant extraction"""
        assert parser.extract_merchant("AIRTEL RECHARGE") == "Airtel"
        assert parser.extract_merchant("JIO PAYMENT") == "Jio"
        assert parser.extract_merchant("VODAFONE BILL") == "Vodafone Idea"

    def test_entertainment_merchants(self):
        """Test entertainment merchant extraction"""
        assert parser.extract_merchant("NETFLIX SUBSCRIPTION") == "Netflix"
        assert parser.extract_merchant("PRIME VIDEO") == "Amazon Prime"
        assert parser.extract_merchant("SPOTIFY PREMIUM") == "Spotify"

    def test_case_insensitive_matching(self):
        """Test case insensitive merchant matching"""
        assert parser.extract_merchant("amazon payment") == "Amazon"
        assert parser.extract_merchant("ZOMATO food") == "Zomato"
        assert parser.extract_merchant("Netflix subscription") == "Netflix"

    def test_no_merchant_found(self):
        """Test when no merchant pattern matches"""
        assert parser.extract_merchant("Unknown Merchant XYZ") is None
        assert parser.extract_merchant("Random Payment") is None
        assert parser.extract_merchant("Cash Withdrawal") is None

class TestFullParsing:
    """Test complete parsing functionality"""

    def test_high_confidence_parsing(self):
        """Test parsing with high confidence (merchant + transaction type)"""
        result = parser.parse("UPI-AMZN12345678-Shopping", Decimal("499.00"), datetime.now())

        assert result.merchant == "Amazon"
        assert result.transaction_type == TransactionTypeEnum.UPI
        assert result.confidence == 0.85
        assert result.parsing_method == "regex_dictionary"
        assert "AMZN Shopping" in result.cleaned_description

    def test_medium_confidence_parsing(self):
        """Test parsing with medium confidence (merchant only)"""
        result = parser.parse("Payment to NETFLIX for subscription", Decimal("199.00"))

        assert result.merchant == "Netflix"
        assert result.transaction_type == TransactionTypeEnum.OTHER
        assert result.confidence == 0.70
        assert result.parsing_method == "dictionary_only"

    def test_low_confidence_parsing(self):
        """Test parsing with low confidence (transaction type only)"""
        result = parser.parse("ATM WDL UNKNOWN BANK", Decimal("500.00"))

        assert result.merchant is None
        assert result.transaction_type == TransactionTypeEnum.ATM
        assert result.confidence == 0.50
        assert result.parsing_method == "transaction_type_only"

    def test_minimal_confidence_parsing(self):
        """Test parsing with minimal confidence (basic cleaning only)"""
        result = parser.parse("Some random unknown payment", Decimal("100.00"))

        assert result.merchant is None
        assert result.transaction_type == TransactionTypeEnum.OTHER
        assert result.confidence == 0.30
        assert result.parsing_method == "basic_cleaning"

    def test_complex_transaction_parsing(self):
        """Test parsing of complex, realistic transaction descriptions"""
        # Real-world example from the task description
        result = parser.parse("NEFT-AXIS BANK-1234-UPI-FOODPANDA", Decimal("450.50"))

        assert result.merchant == "FoodPanda"
        assert result.transaction_type == TransactionTypeEnum.NEFT  # NEFT detected first
        assert result.confidence == 0.85
        assert "FOODPANDA" in result.cleaned_description

class TestLLMIntegration:
    """Test LLM fallback integration"""

    @pytest.mark.asyncio
    async def test_ambiguity_detection(self):
        """Test detection of ambiguous/messy transactions"""
        # Very messy transaction that should trigger LLM
        messy_transaction = "PYT*123ABC#@$%XYZ*UNKNOWN*9876543210"
        result = await parser.parse(messy_transaction, Decimal("100.00"))

        # Should use LLM fallback for very messy transactions
        assert result.parsing_method in ["llm_fallback", "basic_cleaning"]
        assert result.confidence >= 0.0
        assert result.raw_text == messy_transaction

    @pytest.mark.asyncio
    async def test_llm_fallback_with_unclear_merchant(self):
        """Test LLM fallback for unclear merchant names"""
        unclear_cases = [
            "Payment to XYZ Store for groceries",
            "Online purchase from random retailer",
            "Service payment to ABC Company",
            "Transfer to unknown merchant 12345"
        ]

        for case in unclear_cases:
            result = await parser.parse(case, Decimal("50.00"))
            # Should attempt some form of classification
            assert result.confidence >= 0.0
            assert result.category in ["food", "shopping", "other", "transport", "bills", "entertainment"]

    @pytest.mark.asyncio
    async def test_category_classification(self):
        """Test category classification alongside merchant detection"""
        test_cases = [
            ("NETFLIX SUBSCRIPTION", "Netflix", "entertainment"),
            ("ZOMATO FOOD ORDER", "Zomato", "food"),
            ("UBER RIDE PAYMENT", "Uber", "transport"),
            ("AMAZON PURCHASE", "Amazon", "shopping"),
            ("AIRTEL BILL PAYMENT", "Airtel", "bills")
        ]

        for input_text, expected_merchant, expected_category in test_cases:
            result = await parser.parse(input_text, Decimal("100.00"))
            assert result.merchant == expected_merchant
            assert result.category == expected_category
            assert result.confidence > 0.5

class TestAPIEndpoints:
    """Test REST API endpoints"""

    def test_parse_endpoint_success(self):
        """Test successful parsing via API"""
        response = client.post("/parse", json={
            "raw_text": "UPI-AMZN12345-Payment",
            "amount": 299.99,
            "date": "2024-01-15T10:30:00Z"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["merchant"] == "Amazon"
        assert data["transaction_type"] == "UPI"
        assert data["category"] == "shopping"
        assert data["confidence"] == 0.85
        assert data["amount"] == 299.99

    def test_parse_endpoint_minimal_input(self):
        """Test parsing with minimal required input"""
        response = client.post("/parse", json={
            "raw_text": "NETFLIX SUBSCRIPTION"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["merchant"] == "Netflix"
        assert data["category"] == "entertainment"
        assert data["raw_text"] == "NETFLIX SUBSCRIPTION"

    def test_parse_endpoint_validation_error(self):
        """Test validation error for empty raw_text"""
        response = client.post("/parse", json={
            "raw_text": ""
        })

        assert response.status_code == 422  # Validation error

    def test_batch_parse_endpoint(self):
        """Test batch parsing endpoint"""
        response = client.post("/parse/batch", json=[
            {"raw_text": "UPI-AMZN123-Payment", "amount": 199.99},
            {"raw_text": "NEFT-ZOMATO456-Food", "amount": 350.00},
            {"raw_text": "Unknown merchant", "amount": 100.00}
        ])

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["merchant"] == "Amazon"
        assert data[1]["merchant"] == "Zomato"
        assert data[2]["merchant"] is None

    def test_llm_integration_endpoint(self):
        """Test LLM integration through API"""
        # Test with a complex/ambiguous transaction
        response = client.post("/parse", json={
            "raw_text": "Payment to unknown merchant XYZ for services rendered",
            "amount": 150.00
        })

        assert response.status_code == 200
        data = response.json()

        # Should have attempted classification
        assert "llm_used" in data
        assert data["category"] in ["food", "shopping", "other", "transport", "bills", "entertainment"]
        assert data["confidence"] >= 0.0
        assert data["parsing_method"] in ["llm_fallback", "basic_cleaning", "dictionary_only"]

        # Should include LLM usage indicator
        assert isinstance(data["llm_used"], bool)

    def test_batch_parse_size_limit(self):
        """Test batch size limit"""
        large_batch = [{"raw_text": f"Payment {i}"} for i in range(101)]
        response = client.post("/parse/batch", json=large_batch)

        assert response.status_code == 400
        assert "exceed 100" in response.json()["detail"]

    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "transaction-parser"

if __name__ == "__main__":
    # Simple test runner for development
    print("Running transaction parser tests...")

    # Test some key functionality
    import asyncio

    async def run_async_tests():
        test_parser = TestFullParsing()
        await test_parser.test_high_confidence_parsing()
        await test_parser.test_complex_transaction_parsing()

        # Test LLM integration
        test_llm = TestLLMIntegration()
        await test_llm.test_category_classification()

        print("✅ Core parsing tests passed!")

        # Test API
        test_api = TestAPIEndpoints()
        test_api.test_parse_endpoint_success()
        test_api.test_health_endpoint()
        test_api.test_llm_integration_endpoint()

        print("✅ API tests passed!")
        print("All tests completed successfully! 🎉")

    asyncio.run(run_async_tests())

    # Run comprehensive test examples
    print("\n🧪 Running real-world examples with LLM integration:")

    examples = [
        "NEFT-AXIS BANK-1234-UPI-FOODPANDA",
        "IMPS-ZOMATO87654321-Food Delivery",
        "ATM WDL HDFC BANK 12:34:56",
        "NETFLIX Monthly Subscription",
        "Some Unknown Merchant Payment",
        "Payment to XYZ*GROCERY*STORE for food items",  # LLM test case
        "TXN*#@$%UNCLEAR*MERCHANT*789"  # Very messy case
    ]
    
    async def test_examples():
        for example in examples:
            result = await parser.parse(example, Decimal("100.00"))
            print(f"Input: {example}")
            print(f"  → Merchant: {result.merchant}, Category: {result.category}, Type: {result.transaction_type.value}")
            print(f"  → Confidence: {result.confidence}, Method: {result.parsing_method}, LLM: {result.llm_used}")
            print(f"  → Cleaned: {result.cleaned_description}")
            print()
    
    asyncio.run(test_examples())