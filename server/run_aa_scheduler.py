#!/usr/bin/env python3
"""
CLI script to run the AA sync scheduler

Usage:
    python run_aa_scheduler.py

Environment Variables:
    REDIS_URL: Redis connection URL (default: redis://localhost:6379/0)
    DATABASE_URL: PostgreSQL connection URL
    AA_SCHEDULER_ENABLED: Enable scheduler (default: true)
    AA_SYNC_INTERVAL_HOURS: Sync interval in hours (default: 4)
    AA_STALE_THRESHOLD_HOURS: Hours before account is considered stale (default: 4)
"""

import asyncio
import logging
import os
import sys

# Add the server directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.scheduler.aa_scheduler import AAScheduler, simple_scheduler_loop
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

    # Run the scheduler
    try:
        print("🕒 AA Scheduler starting. Press Ctrl+C to stop.")
        await simple_scheduler_loop()
    except KeyboardInterrupt:
        print("\n⏹️ Shutting down scheduler...")
    finally:
        await pool.close()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(main())