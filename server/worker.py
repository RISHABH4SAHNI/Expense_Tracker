#!/usr/bin/env python3
"""
Standalone RQ Worker Script for Transaction Categorization

Usage:
    python worker.py

Environment Variables:
    REDIS_URL: Redis connection URL (default: redis://localhost:6379)
    DATABASE_URL: PostgreSQL connection URL
"""

import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.workers.rq_worker import run_worker

if __name__ == '__main__':
    print("🚀 Starting Expense Tracker RQ Worker...")
    print("📋 Listening for jobs on 'categorize' queue")
    print("🛑 Press Ctrl+C to stop")
    print("-" * 50)

    try:
        run_worker()
    except KeyboardInterrupt:
        print("\n🛑 Worker stopped by user")
    except Exception as e:
        print(f"❌ Worker error: {e}")
        sys.exit(1)