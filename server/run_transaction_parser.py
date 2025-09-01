"""
Transaction Parser Service Runner

Utility script to run and test the transaction parser microservice.

Usage:
    python run_transaction_parser.py                    # Start server
    python run_transaction_parser.py --test            # Run tests
    python run_transaction_parser.py --demo            # Run demo
"""

import argparse
import asyncio
import json
import requests
from datetime import datetime
from decimal import Decimal

def test_parser_examples():
    """Test the parser with various real-world examples"""

    base_url = "http://localhost:8001"

    # Test cases from the task description and real scenarios
    test_cases = [
        {
            "description": "Task example - NEFT with UPI merchant",
            "raw_text": "NEFT-AXIS BANK-1234-UPI-FOODPANDA",
            "amount": 450.50,
            "expected_merchant": "FoodPanda"
        },
        {
            "description": "Amazon UPI payment",
            "raw_text": "UPI-AMZN12345678-Shopping Payment",
            "amount": 1299.99,
            "expected_merchant": "Amazon"
        },
        {
            "description": "Zomato food order",
            "raw_text": "IMPS-ZOMATO87654321-Food Delivery",
            "amount": 385.50,
            "expected_merchant": "Zomato"
        },
        {
            "description": "Netflix subscription",
            "raw_text": "NETFLIX MONTHLY SUBSCRIPTION 01/15/24",
            "amount": 199.00,
            "expected_merchant": "Netflix"
        },
        {
            "description": "Uber ride payment",
            "raw_text": "UPI/UBER/RIDE PAYMENT",
            "amount": 175.25,
            "expected_merchant": "Uber"
        },
        {
            "description": "ATM withdrawal (no merchant)",
            "raw_text": "ATM WDL HDFC BANK 12:34:56",
            "amount": 2000.00,
            "expected_merchant": None
        },
        {
            "description": "Unknown merchant",
            "raw_text": "Payment to Random Shop XYZ",
            "amount": 50.00,
            "expected_merchant": None
        }
    ]

    print("🧪 Testing Transaction Parser with real-world examples...\n")

    for i, case in enumerate(test_cases, 1):
        print(f"Test {i}: {case['description']}")
        print(f"Input: {case['raw_text']}")

        try:
            response = requests.post(f"{base_url}/parse", json={
                "raw_text": case["raw_text"],
                "amount": case["amount"],
                "date": datetime.now().isoformat()
            })

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Merchant: {result['merchant']} (expected: {case['expected_merchant']})")
                print(f"   Type: {result['transaction_type']}, Confidence: {result['confidence']}")
                print(f"   Cleaned: {result['cleaned_description']}")

                # Validation
                if result['merchant'] == case['expected_merchant']:
                    print("   ✅ PASS - Merchant extraction correct")
                else:
                    print(f"   ❌ FAIL - Expected {case['expected_merchant']}, got {result['merchant']}")
            else:
                print(f"❌ API Error: {response.status_code}")

        except requests.exceptions.ConnectionError:
            print("❌ Connection failed - is the server running on port 8001?")
            print("   Start server with: python transaction_parser.py")
            return
        except Exception as e:
            print(f"❌ Error: {e}")

        print("-" * 60)

def main():
    parser = argparse.ArgumentParser(description="Transaction Parser Service Runner")
    parser.add_argument("--test", action="store_true", help="Run API tests against running server")
    parser.add_argument("--demo", action="store_true", help="Run demonstration with sample data")
    parser.add_argument("--port", type=int, default=8001, help="Port to run server on")

    args = parser.parse_args()

    if args.test or args.demo:
        print("Testing Transaction Parser Microservice")
        print("=" * 50)
        test_parser_examples()

    else:
        print("Starting Transaction Parser Microservice...")
        print(f"🚀 Server will start on http://localhost:{args.port}")
        print("📖 API Documentation: http://localhost:{}/docs".format(args.port))
        print("\nTest the service with:")
        print(f"  python {__file__} --test")
        print("\nStop server with Ctrl+C")

        import uvicorn
        from transaction_parser import app
        uvicorn.run(app, host="0.0.0.0", port=args.port)

if __name__ == "__main__":
    main()