#!/usr/bin/env python3
"""
Integration test showing how the categorizer works with the existing parsing system.
This demonstrates the full pipeline from raw transaction to categorized merchant.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the server directory to the path
sys.path.append(str(Path(__file__).parent))

# Import existing components
from app.services.parser import parse_transaction, _apply_regex_normalizers, _lookup_merchant

# Import our simple categorizer
from test_categorizer_simple import SimpleMerchantCategorizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def test_full_pipeline():
    """Test the full transaction processing pipeline"""
    
    print("🚀 Testing Full Transaction Processing Pipeline")
    print("Raw Transaction → Parser → Categorizer → Final Result")
    print("=" * 70)
    
    # Initialize categorizer
    categorizer = SimpleMerchantCategorizer()
    
    # Test cases with raw transaction descriptions
    test_transactions = [
        "UPI-ZOMATO12345-Food delivery payment",
        "NEFT-AXIS BANK-1234-AMAZON PURCHASE",
        "IMPS-HDFC-5678-NETFLIX SUBSCRIPTION", 
        "ATM WDL SBI 12:34:56",
        "UPI-PHONEPE-UBER RIDE BOOKING",
        "SALARY CREDIT FROM COMPANY XYZ",
        "Some Random Local Merchant Payment",
        "BIGBASKET GROCERY ORDER",
        "APOLLO HOSPITAL CONSULTATION"
    ]
    
    for raw_transaction in test_transactions:
        print(f"\n📋 Processing: {raw_transaction}")
        print("-" * 50)
        
        try:
            # Step 1: Parse the transaction
            parse_result = await parse_transaction(raw_transaction)
            
            print(f"✅ Parser Result:")
            print(f"   Cleaned: {parse_result['cleaned_desc']}")
            print(f"   Merchant: {parse_result['merchant_candidate']}")
            print(f"   Category: {parse_result['category_candidate']}")
            print(f"   Confidence: {parse_result['confidence']}")
            
            # Step 2: If parser didn't find a merchant or has low confidence, use categorizer
            use_categorizer = (
                parse_result['merchant_candidate'] is None or 
                parse_result['confidence'] < 0.7
            )
            
            if use_categorizer:
                # Use the cleaned description for better categorization
                merchant_text = parse_result['merchant_candidate'] or parse_result['cleaned_desc']
                cat_result = categorizer.categorize_merchant(merchant_text)
                
                print(f"🤖 Categorizer Result:")
                print(f"   Category: {cat_result['category']}")
                print(f"   Confidence: {cat_result['confidence']:.3f}")
                print(f"   Needs Feedback: {cat_result['needs_feedback']}")
                print(f"   Method: {cat_result['reasoning']}")
                
                # Final result combines both
                final_category = cat_result['category']
                final_confidence = max(parse_result['confidence'], cat_result['confidence'])
            else:
                print(f"✅ Parser confidence sufficient, using parser result")
                final_category = parse_result['category_candidate']
                final_confidence = parse_result['confidence']
            
            print(f"🎯 Final Result:")
            print(f"   Merchant: {parse_result['merchant_candidate'] or 'Unknown'}")
            print(f"   Category: {final_category}")
            print(f"   Final Confidence: {final_confidence:.3f}")
            
        except Exception as e:
            print(f"❌ Error processing {raw_transaction}: {e}")
    
    print("\n" + "=" * 70)
    print("✅ Full pipeline test completed!")
    print("\n💡 Key Benefits of the Categorizer:")
    print("   • Handles merchants not in the knowledge base")
    print("   • Provides fallback categorization using similarity")
    print("   • Flags transactions needing user feedback")
    print("   • Can be improved through user corrections")
    print("   • Works with existing parser infrastructure")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
