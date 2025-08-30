#!/usr/bin/env python3
"""
CLI script to run the AA sync worker

Usage:
    python run_aa_worker.py

Environment Variables:
    REDIS_URL: Redis connection URL (default: redis://localhost:6379/0)
    DATABASE_URL: PostgreSQL connection URL
    AA_WORKER_MAX_RETRIES: Maximum retries per job (default: 3)
"""

import asyncio
import logging
import os
import sys

# Add the server directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.workers.aa_worker import AAWorker
from app.database import set_db_pool
import asyncpg

async def main():
    # Set up database connection
    database_url = os.getenv("DATABASE_URL", "postgresql://expenseuser:expensepass@localhost:5433/expensedb")
    try:
        pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
        set_db_pool(pool)
        print("✅ Database connection established")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return

    # Run the worker
    worker = AAWorker()

    try:
        await worker.connect()
        print("🚀 AA Worker started. Press Ctrl+C to stop.")
        await worker.run_worker()
    except KeyboardInterrupt:
        print("\n⏹️ Shutting down worker...")
    finally:
        await worker.stop()
        await pool.close()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(main())