#!/usr/bin/env python3
"""
Test script for the embeddings wrapper.
Tests the basic functionality without requiring a database connection.
"""

import asyncio
import numpy as np
from pathlib import Path
import tempfile
import os
import sys

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent))

from app.services.embeddings import EmbeddingsIndex
from app.services.merchant_similarity import MerchantSimilarityService

async def test_basic_embeddings():
    """Test basic embeddings functionality"""
    print("🧪 Testing basic embeddings functionality...")

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        embeddings = EmbeddingsIndex()

        # Initialize
        success = await embeddings.init_embeddings_index(os.path.join(temp_dir, "test.db"))
        assert success, "Failed to initialize embeddings"

        backend_info = embeddings.get_backend_info()
        print(f"✅ Initialized with backend: {backend_info['backend']}")

        # Test merchant names
        test_merchants = [
            "Starbucks Coffee",
            "Starbucks Corporation",
            "McDonald's Restaurant",
            "McDonalds Fast Food",
            "Amazon.com",
            "Amazon Prime",
            "Walmart Store",
            "Target Corporation"
        ]

        # Add merchants
        print("📝 Adding test merchants...")
        for merchant in test_merchants:
            success = await embeddings.upsert_merchant_embedding(merchant)
            assert success, f"Failed to add merchant: {merchant}"

        print(f"✅ Added {len(test_merchants)} merchants")

        # Test similarity search
        print("\n🔍 Testing similarity search...")
        query_merchant = "Starbucks Cafe"
        query_vector = await embeddings._generate_embedding(query_merchant)

        results = await embeddings.query_nearest(query_vector, k=3)

        print(f"Query: '{query_merchant}'")
        print("Similar merchants:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result.merchant} (score: {result.score:.3f})")

        # Verify we get Starbucks-related results at the top
        assert any("starbucks" in result.merchant.lower() for result in results[:2]), \
            "Expected Starbucks-related results at the top"

        print("✅ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_basic_embeddings())
#!/usr/bin/env python3
"""
Test script for the embeddings wrapper.
Tests the basic functionality without requiring a database connection.
"""

import asyncio
import numpy as np
from pathlib import Path
import tempfile
import os
import sys

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent))

from app.services.embeddings import EmbeddingsIndex
from app.services.merchant_similarity import MerchantSimilarityService

async def test_basic_embeddings():
    """Test basic embeddings functionality"""
    print("🧪 Testing basic embeddings functionality...")

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        embeddings = EmbeddingsIndex()

        # Initialize
        success = await embeddings.init_embeddings_index(os.path.join(temp_dir, "test.db"))
        assert success, "Failed to initialize embeddings"

        backend_info = embeddings.get_backend_info()
        print(f"✅ Initialized with backend: {backend_info['backend']}")

        # Test merchant names
        test_merchants = [
            "Starbucks Coffee",
            "Starbucks Corporation",
            "McDonald's Restaurant",
            "McDonalds Fast Food",
            "Amazon.com",
            "Amazon Prime",
            "Walmart Store",
            "Target Corporation"
        ]

        # Add merchants
        print("📝 Adding test merchants...")
        for merchant in test_merchants:
            success = await embeddings.upsert_merchant_embedding(merchant)
            assert success, f"Failed to add merchant: {merchant}"

        print(f"✅ Added {len(test_merchants)} merchants")

        # Test similarity search
        print("\n🔍 Testing similarity search...")
        query_merchant = "Starbucks Cafe"
        query_vector = await embeddings._generate_embedding(query_merchant)

        results = await embeddings.query_nearest(query_vector, k=3)

        print(f"Query: '{query_merchant}'")
        print("Similar merchants:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result.merchant} (score: {result.score:.3f})")

        # Verify we get Starbucks-related results at the top
        assert any("starbucks" in result.merchant.lower() for result in results[:2]), \
            "Expected Starbucks-related results at the top"

        print("✅ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_basic_embeddings())