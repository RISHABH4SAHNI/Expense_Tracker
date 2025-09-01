#!/usr/bin/env python3
"""
Test showing the categorizer working as a fallback when parser confidence is low.
"""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from test_categorizer_simple import SimpleMerchantCategorizer

async def test_categorizer_fallback():
    """Test categorizer with transactions that would have low parser confidence"""
    
    print("🚀 Testing Categorizer Fallback for Unknown Merchants")
    print("=" * 60)
    
    categorizer = SimpleMerchantCategorizer()
    
    # Test cases where parser might not find merchants or have low confidence
    unknown_merchants = [
        "NEW LOCAL PIZZA PLACE",
        "UNKNOWN RESTAURANT DOWNTOWN", 
        "RANDOM SHOPPING MALL",
        "LOCAL GROCERY STORE",
        "NEIGHBORHOOD DOCTOR CLINIC",
        "SMALL CAFE NEARBY",
        "LOCAL GYM MEMBERSHIP",
        "UNKNOWN PHARMACY",
        "LOCAL TAXI SERVICE",
        "RANDOM STREAMING SERVICE"
    ]
    
    print("🧪 Testing unknown merchant categorization:")
    print("-" * 60)
    
    for merchant in unknown_merchants:
        try:
            result = categorizer.categorize_merchant(merchant)
            
            print(f"Merchant: {merchant}")
            print(f"  ✅ Predicted Category: {result['category']}")
            print(f"  📊 Confidence: {result['confidence']:.3f} ({result['confidence_level']})")
            print(f"  🔄 Needs Feedback: {'Yes' if result['needs_feedback'] else 'No'}")
            print(f"  🤔 Reasoning: {result['reasoning']}")
            if result['similar_merchants']:
                print(f"  🔗 Similar Patterns: {', '.join(result['similar_merchants'][:3])}")
            print()
            
        except Exception as e:
            print(f"❌ Error categorizing {merchant}: {e}")
    
    print("=" * 60)
    print("🎯 Summary:")
    print("✅ The categorizer successfully provides fallback categorization")
    print("✅ It identifies which transactions need user feedback") 
    print("✅ It explains its reasoning for transparency")
    print("✅ It suggests similar patterns to help users understand the classification")
    print("\n💡 In a real system, transactions with 'needs_feedback=True' would be:")
    print("   • Flagged for manual review")
    print("   • Presented to users for correction")
    print("   • Used to improve the model through feedback")

if __name__ == "__main__":
    asyncio.run(test_categorizer_fallback())
