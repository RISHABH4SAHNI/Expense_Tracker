#!/usr/bin/env python3
"""
Simple test for merchant categorizer that bypasses sentence transformers issue.
Uses basic TF-IDF similarity for demonstration.
"""

import asyncio
import logging
from pathlib import Path
import sys
import json
import numpy as np
from typing import Dict, List, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class SimpleMerchantCategorizer:
    """Simple merchant categorizer using TF-IDF and predefined patterns"""
    
    def __init__(self):
        self.category_patterns = {
            "food": ["restaurant", "food", "dining", "cafe", "pizza", "burger", "coffee", "zomato", "swiggy", "mcdonald", "kfc", "starbucks"],
            "transport": ["transport", "taxi", "uber", "ola", "flight", "train", "bus", "metro", "fuel", "petrol", "irctc"],
            "shopping": ["shopping", "store", "mall", "amazon", "flipkart", "myntra", "bigbasket", "retail", "electronics"],
            "entertainment": ["netflix", "spotify", "movie", "music", "streaming", "cinema", "bookmyshow", "entertainment"],
            "bills": ["bill", "electricity", "water", "gas", "internet", "phone", "mobile", "airtel", "jio", "vodafone"],
            "healthcare": ["hospital", "pharmacy", "doctor", "medical", "healthcare", "apollo", "medicine"],
            "education": ["school", "college", "course", "education", "byju", "unacademy", "learning"],
            "salary": ["salary", "income", "payroll", "wages", "compensation"],
            "investment": ["investment", "dividend", "interest", "mutual", "stocks", "trading"],
            "other": ["transfer", "withdrawal", "atm", "bank", "upi", "neft", "payment"]
        }
        
        # Create combined text for each category
        self.category_texts = {
            category: " ".join(patterns) 
            for category, patterns in self.category_patterns.items()
        }
        
        # Initialize TF-IDF vectorizer
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        
        # Load merchant knowledge base
        self.kb_path = Path(__file__).parent / "app" / "services" / "merchant_kb.json"
        self.merchant_kb = {}
        self._load_kb()
        
        # Pre-fit the vectorizer with category texts
        all_texts = list(self.category_texts.values())
        self.category_vectors = self.vectorizer.fit_transform(all_texts)
        self.category_names = list(self.category_texts.keys())
        
        logger.info(f"✅ Simple categorizer initialized with {len(self.category_names)} categories")
    
    def _load_kb(self):
        """Load merchant knowledge base if available"""
        try:
            if self.kb_path.exists():
                with open(self.kb_path, 'r') as f:
                    self.merchant_kb = json.load(f)
                logger.info(f"Loaded merchant KB")
        except Exception as e:
            logger.warning(f"Could not load merchant KB: {e}")
    
    def categorize_merchant(self, merchant: str) -> Dict:
        """Categorize a merchant name"""
        merchant_lower = merchant.lower()
        
        # First check knowledge base patterns
        kb_result = self._check_knowledge_base(merchant)
        if kb_result:
            return kb_result
        
        # Use TF-IDF similarity
        try:
            merchant_vector = self.vectorizer.transform([merchant_lower])
            similarities = cosine_similarity(merchant_vector, self.category_vectors)[0]
            
            best_idx = np.argmax(similarities)
            best_similarity = similarities[best_idx]
            best_category = self.category_names[best_idx]
            
            if best_similarity >= 0.3:
                confidence_level = "high" if best_similarity >= 0.7 else "medium" if best_similarity >= 0.5 else "low"
                return {
                    "category": best_category,
                    "confidence": float(best_similarity),
                    "confidence_level": confidence_level,
                    "needs_feedback": best_similarity < 0.5,
                    "reasoning": f"TF-IDF similarity: {best_similarity:.3f}",
                    "similar_merchants": self.category_patterns[best_category][:3]
                }
            else:
                return {
                    "category": "unknown",
                    "confidence": 0.0,
                    "confidence_level": "unknown",
                    "needs_feedback": True,
                    "reasoning": f"Low similarity ({best_similarity:.3f}) to all categories",
                    "similar_merchants": []
                }
                
        except Exception as e:
            logger.error(f"Error in TF-IDF categorization: {e}")
            return {
                "category": "other",
                "confidence": 0.0,
                "confidence_level": "unknown",
                "needs_feedback": True,
                "reasoning": f"Error: {str(e)}",
                "similar_merchants": []
            }
    
    def _check_knowledge_base(self, merchant: str) -> Optional[Dict]:
        """Check merchant against knowledge base patterns"""
        if not self.merchant_kb.get('merchant_patterns'):
            return None
        
        merchant_upper = merchant.upper()
        
        # Check all pattern groups
        for group_name, patterns in self.merchant_kb['merchant_patterns'].items():
            for pattern, data in patterns.items():
                if pattern in merchant_upper or merchant_upper in pattern:
                    confidence = data.get('confidence', 0.8)
                    category = data.get('category', 'other')
                    
                    return {
                        "category": category,
                        "confidence": confidence,
                        "confidence_level": "high" if confidence >= 0.8 else "medium",
                        "needs_feedback": False,
                        "reasoning": f"Knowledge base match: {pattern}",
                        "similar_merchants": [data.get('name', pattern)]
                    }
        
        return None

async def test_simple_categorizer():
    """Test the simple categorizer"""
    
    print("🚀 Testing Simple Merchant Categorizer")
    print("=" * 50)
    
    categorizer = SimpleMerchantCategorizer()
    
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
            result = categorizer.categorize_merchant(merchant)
            
            print(f"Merchant: {merchant}")
            print(f"  Category: {result['category']}")
            print(f"  Confidence: {result['confidence']:.3f} ({result['confidence_level']})")
            print(f"  Needs Feedback: {result['needs_feedback']}")
            if result['similar_merchants']:
                print(f"  Similar: {', '.join(result['similar_merchants'][:3])}")
            print(f"  Reasoning: {result['reasoning']}")
            print()
            
        except Exception as e:
            print(f"❌ Error categorizing {merchant}: {e}")
    
    print("✅ Simple categorizer test completed!")

if __name__ == "__main__":
    asyncio.run(test_simple_categorizer())
