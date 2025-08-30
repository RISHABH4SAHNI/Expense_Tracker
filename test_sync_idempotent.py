#!/usr/bin/env python3
"""
Test script to verify idempotent sync functionality.

This script demonstrates that running sync twice results in:
- First run: inserts new transactions
- Second run: skips all transactions (0 inserted)

Run with: python test_sync_idempotent.py
"""

import asyncio
import os
import sys
import asyncpg
from datetime import datetime, timedelta

# Add server directory to path
sys.path.append('./server')

from app.services.sync import sync_account, normalize_tx_id, upsert_transaction
from app.services.aa_client import aa_client

async def test_idempotent_sync():
    """Test that sync operations are idempotent (safe to run multiple times)."""

    print("🧪 Testing Idempotent Sync Operations")
    print("=" * 50)

    # Database connection
    database_url = os.getenv("DATABASE_URL", "postgresql://expenseuser:expensepass@localhost:5433/expensedb")

    try:
        pool = await asyncpg.create_pool(database_url, min_size=1, max_size=3)
        print("✅ Connected to database")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("Make sure PostgreSQL is running: docker-compose up -d postgres")
        return

    async with pool.acquire() as conn:

        # Test 1: Verify normalize_tx_id creates consistent hashes
        print("\n📊 Test 1: Hash Consistency")
        sample_tx = {
            "id": "test_tx_123",
            "account_id": "test_account_456", 
            "amount": 150.50,
            "ts": "2024-01-15T10:30:00+05:30",
            "user_id": "test_user_789"
        }

        hash1 = normalize_tx_id(sample_tx)
        hash2 = normalize_tx_id(sample_tx)
        hash3 = normalize_tx_id({**sample_tx, "amount": 150.51})  # Different amount

        print(f"Same transaction hash 1: {hash1}")
        print(f"Same transaction hash 2: {hash2}")
        print(f"Different amount hash:   {hash3}")

        assert hash1 == hash2, "Same transaction should produce same hash"
        assert hash1 != hash3, "Different transaction should produce different hash"
        print("✅ Hash consistency test passed")

        # Test 2: Create a mock account for testing
        print("\n🏦 Test 2: Mock Account Setup")
        test_user_id = "test_user_sync_demo"
        test_account = {
            "id": "test_aa_account_uuid",
            "user_id": test_user_id,
            "aa_account_id": "mock_test_account_123",
            "display_name": "Test Bank Account"
        }

        # Clean up any existing test data
        await conn.execute("DELETE FROM transactions WHERE user_id = $1", test_user_id)
        await conn.execute("DELETE FROM aa_sync_logs WHERE user_id = $1", test_user_id)
        print("🧹 Cleaned up existing test data")

        # Test 3: First sync - should insert transactions
        print("\n🔄 Test 3: First Sync (should insert)")
        since_date = datetime.utcnow() - timedelta(days=7)

        first_result = await sync_account(test_account, since_date, conn)
        print(f"First sync result: {first_result}")

        first_inserted = first_result.get("inserted_count", 0)
        first_skipped = first_result.get("skipped_count", 0)

        print(f"✅ First sync: {first_inserted} inserted, {first_skipped} skipped")

        # Test 4: Second sync - should skip all (idempotent)
        print("\n🔄 Test 4: Second Sync (should skip all)")

        second_result = await sync_account(test_account, since_date, conn)
        print(f"Second sync result: {second_result}")

        second_inserted = second_result.get("inserted_count", 0)
        second_skipped = second_result.get("skipped_count", 0)

        print(f"✅ Second sync: {second_inserted} inserted, {second_skipped} skipped")

        # Verification
        if second_inserted == 0 and second_skipped > 0:
            print("\n🎉 IDEMPOTENT TEST PASSED!")
            print("✅ Second run inserted 0 new transactions")
            print("✅ All transactions were correctly skipped as duplicates")
        else:
            print("\n❌ IDEMPOTENT TEST FAILED!")
            print(f"Expected 0 inserted, got {second_inserted}")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(test_idempotent_sync())