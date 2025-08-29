#!/usr/bin/env python3
"""
CLI script to build and test the merchant embeddings index.

Usage:
    python build_embeddings.py --help
    python build_embeddings.py build
    python build_embeddings.py test "Starbucks Coffee"
    python build_embeddings.py info
"""

import asyncio
import asyncpg
import argparse
import os
from pathlib import Path
import sys

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent))

from app.services.merchant_similarity import MerchantSimilarityService
from app.services.embeddings import EmbeddingsIndex

async def build_index():
    """Build embeddings index from database transactions"""
    print("🔄 Building embeddings index from transactions...")

    # Database connection
    try:
        DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://expenseuser:expensepass@localhost:5432/expensedb")
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Connected to database")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        print("Make sure your database is running and DATABASE_URL is set correctly")
        return

    # Initialize service
    service = MerchantSimilarityService("./data/merchants.db")
    if not await service.initialize():
        print("❌ Failed to initialize merchant similarity service")
        return

    # Build index
    try:
        stats = await service.build_index_from_transactions(conn)
        print(f"✅ Index building complete!")
        print(f"   Processed: {stats['processed']}")
        print(f"   Indexed: {stats['indexed']}")
        print(f"   Errors: {stats['errors']}")
    except Exception as e:
        print(f"❌ Error building index: {e}")
    finally:
        await conn.close()

async def test_similarity(merchant_name: str):
    """Test similarity search for a merchant"""
    print(f"🔍 Testing similarity search for: '{merchant_name}'")

    service = MerchantSimilarityService("./data/merchants.db")
    if not await service.initialize():
        print("❌ Failed to initialize service")
        return

    results = await service.find_similar_merchants(merchant_name, k=5)

    if results:
        print(f"Found {len(results)} similar merchants:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result.merchant} (score: {result.score:.3f})")
    else:
        print("No similar merchants found")

async def show_info():
    """Show service information"""
    service = MerchantSimilarityService("./data/merchants.db")
    await service.initialize()

    info = await service.get_service_info()
    print("📊 Merchant Similarity Service Info:")
    for key, value in info.items():
        print(f"   {key}: {value}")

def main():
    parser = argparse.ArgumentParser(description="Merchant embeddings CLI")
    parser.add_argument("command", choices=["build", "test", "info"], 
                       help="Command to run")
    parser.add_argument("merchant", nargs="?", 
                       help="Merchant name for testing (required for 'test' command)")

    args = parser.parse_args()

    if args.command == "build":
        asyncio.run(build_index())
    elif args.command == "test":
        if not args.merchant:
            print("❌ Merchant name required for 'test' command")
            return
        asyncio.run(test_similarity(args.merchant))
    elif args.command == "info":
        asyncio.run(show_info())

if __name__ == "__main__":
    main()