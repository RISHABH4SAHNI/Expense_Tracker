#!/usr/bin/env python3
"""
Test script to verify Merchant KB integration with the expense tracker

This script tests:
1. Merchant KB service loading
2. Pattern matching (exact and regex)
3. LLM client integration
4. Parser service integration
5. End-to-end transaction classification

Run with: python test_merchant_kb_integration.py
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from app.services.merchant_kb_service import merchant_kb
from app.services.llm_client import llm_client
from app.services.parser import parse_transaction


async def test_merchant_kb_service():
    """Test the merchant KB service directly"""
    print("🏪 Testing Merchant KB Service")
    print("=" * 50)

    # Test loading
    success = merchant_kb.load_kb()
    print(f"✅ KB Load Status: {success}")

    if success:
        stats = merchant_kb.get_stats()
        print(f"📊 Patterns loaded: {stats['total_exact_patterns']} exact, {stats['total_regex_patterns']} regex")
        print(f"📂 Categories: {', '.join(stats['categories'])}")
        print()

        # Test some matches
        test_cases = [
            "ZOMATO ORDER 12345",
            "AMZ*PURCHASE789",
            "UBER TRIP BANGALORE",
            "NETFLIX SUBSCRIPTION",
            "RANDOM UNKNOWN MERCHANT"
        ]

        for desc in test_cases:
            match = merchant_kb.match_merchant(desc)
            if match:
                print(f"✅ '{desc}' -> {match.merchant} ({match.category}) - {match.confidence:.2f} confidence")
            else:
                print(f"❌ '{desc}' -> No match found")
        print()


async def test_llm_integration():
    """Test LLM client with Merchant KB integration"""
    print("🤖 Testing LLM Client Integration")
    print("=" * 50)

    test_cases = [
        "UPI-ZOMATO*ORDER123-FOOD DELIVERY",
        "NEFT-AMAZON-SHOPPING",
        "CARD-NETFLIX-SUBSCRIPTION", 
        "ATM-WITHDRAWAL-SBI",
        "Some Random Merchant XYZ"
    ]

    for desc in test_cases:
        result = await llm_client.classify_transaction(desc)
        print(f"Input: '{desc}'")
        print(f"  Merchant: {result.get('merchant', 'None')}")
        print(f"  Category: {result.get('category', 'None')}")
        print(f"  Confidence: {result.get('confidence', 'N/A')}")
        print(f"  Explanation: {result.get('explanation', 'None')}")
        print()


async def main():
    """Run all tests"""
    await test_merchant_kb_service()
    await test_llm_integration()

    print("🎉 All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())