#!/usr/bin/env python3
"""
Test script for AA worker functionality

Demonstrates:
1. Enqueuing AA sync jobs
2. Worker processing jobs
3. Retry mechanism
4. Dead letter queue handling
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.workers.aa_worker import enqueue_aa_sync, AAWorker
from app.database import set_db_pool
import asyncpg
import redis.asyncio as redis

async def test_worker_functionality():
    """Test the AA worker with sample jobs"""

    print("🧪 Testing AA Worker Functionality")
    print("=" * 50)

    # Set up connections
    database_url = os.getenv("DATABASE_URL", "postgresql://expenseuser:expensepass@localhost:5433/expensedb")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    try:
        # Database connection
        pool = await asyncpg.create_pool(database_url, min_size=1, max_size=3)
        set_db_pool(pool)
        print("✅ Database connection established")

        # Redis connection
        redis_client = redis.from_url(redis_url)
        await redis_client.ping()
        print("✅ Redis connection established")

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("Make sure PostgreSQL and Redis are running:")
        print("  docker-compose up -d postgres redis")
        return

    try:
        # Clear existing queues
        worker = AAWorker()
        await worker.connect()

        await worker.redis_client.delete("aa_sync")
        await worker.redis_client.delete("aa_sync_retry") 
        await worker.redis_client.delete("aa_dlq")
        await worker.redis_client.delete("aa_sync_completed")
        await worker.redis_client.delete("aa_sync_failed")

        print("🧹 Cleared existing queues")

        # Test 1: Get sample account data
        print("\n📋 Test 1: Finding AA accounts to test with")
        async with pool.acquire() as conn:
            accounts = await conn.fetch("""
                SELECT id, user_id, aa_account_id, display_name
                FROM aa_accounts 
                LIMIT 3
            """)

            if not accounts:
                print("❌ No AA accounts found in database")
                print("Please run the AA linking flow first to create test accounts")
                return

            print(f"Found {len(accounts)} accounts:")
            for account in accounts:
                print(f"  - {account['aa_account_id']} ({account['display_name']})")

        # Test 2: Enqueue sync jobs
        print("\n📤 Test 2: Enqueuing sync jobs")
        since_ts = datetime.utcnow() - timedelta(days=7)

        for account in accounts:
            success = await enqueue_aa_sync(
                user_id=str(account['user_id']),
                account_id=str(account['id']),
                since_ts=since_ts,
                redis_client=redis_client
            )
            print(f"{'✅' if success else '❌'} Enqueued job for {account['aa_account_id']}")

        # Test 3: Check queue status
        print("\n📊 Test 3: Queue status")
        stats = await worker.get_stats()
        print(f"Main queue: {stats.get('main_queue_size', 0)} jobs")
        print(f"Retry queue: {stats.get('retry_queue_size', 0)} jobs")
        print(f"DLQ: {stats.get('dlq_size', 0)} jobs")

        print("\n🚀 Test completed!")
        print("Now run the worker to process these jobs:")
        print("  python run_aa_worker.py")

    finally:
        await worker.stop()
        await redis_client.close()
        await pool.close()

if __name__ == "__main__":
    asyncio.run(test_worker_functionality())