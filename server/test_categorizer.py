#!/usr/bin/env python3
"""
Test script for the merchant categorizer module.

This script demonstrates how to use the MerchantCategorizer for classifying
merchants into categories using embeddings and similarity matching.
"""

import asyncio
import logging
from pathlib import Path
import sys

# Add the server directory to the path
sys.path.append(str(Path(__file__).parent))

from app.services.categorizer import MerchantCategorizer, categorizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_categorizer():
    """Test the merchant categorizer with various merchant names"""

    print("🚀 Testing Merchant Categorizer")
    print("=" * 50)

    # Initialize the categorizer
    print("Initializing categorizer...")
    success = await categorizer.initialize()
    if not success:
        print("❌ Failed to initialize categorizer")
        return

    print("✅ Categorizer initialized successfully")

    # Get stats
    stats = await categorizer.get_stats()
    print(f"📊 Stats: {stats}")
    print()

    # Test merchants
    test_merchants = [
        "ZOMATO ORDER 12345",
        "STARBUCKS COFFEE",
        "AMAZON PURCHASE",
        "UBER TRIP",
        "NETFLIX SUBSCRIPTION",
        "ELECTRICITY BILL PAYMENT",
        "APOLLO HOSPITAL",
        "BYJU'S LEARNING",
        "SALARY CREDIT",
        "UNKNOWN MERCHANT XYZ",
        "LOCAL RESTAURANT ABC",
        "GROCERY STORE DEF"
    ]

    print("🧪 Testing categorization:")
    print("-" * 50)

    for merchant in test_merchants:
        try:
            result = await categorizer.categorize_merchant(merchant)

            print(f"Merchant: {merchant}")
            print(f"  Category: {result.category}")
            print(f"  Confidence: {result.confidence:.3f} ({result.confidence_level.value})")
            print(f"  Needs Feedback: {result.needs_feedback}")
            if result.similar_merchants:
                print(f"  Similar: {', '.join(result.similar_merchants[:3])}")
            if result.reasoning:
                print(f"  Reasoning: {result.reasoning}")
            print()

        except Exception as e:
            print(f"❌ Error categorizing {merchant}: {e}")

    # Test feedback mechanism
    print("🔄 Testing feedback mechanism:")
    await categorizer.add_feedback("LOCAL RESTAURANT ABC", "food", "test_user")
    result_after_feedback = await categorizer.categorize_merchant("LOCAL RESTAURANT ABC")
    print(f"After feedback - Category: {result_after_feedback.category}, Confidence: {result_after_feedback.confidence:.3f}")

if __name__ == "__main__":
    asyncio.run(test_categorizer())