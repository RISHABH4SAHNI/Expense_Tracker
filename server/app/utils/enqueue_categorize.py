"""
Helper script to enqueue transaction categorization jobs
"""

import os
import redis
from rq import Queue, Connection
import logging

logger = logging.getLogger(__name__)

def enqueue_categorize(tx_id: str) -> bool:
    """
    Enqueue a transaction categorization job

    Args:
        tx_id: Bank transaction ID to process

    Returns:
        bool: True if successfully enqueued, False otherwise
    """
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_conn = redis.from_url(redis_url)

        # Create queue
        queue = Queue('categorize', connection=redis_conn)

        # Import the job function
        from app.workers.rq_worker import categorize_transaction_job

        # Enqueue the job
        job = queue.enqueue(categorize_transaction_job, tx_id)

        logger.info(f"✅ Enqueued categorization job for transaction {tx_id}, job ID: {job.id}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to enqueue categorization job for {tx_id}: {e}")
        return False

def enqueue_bulk_categorize(tx_ids: list) -> int:
    """
    Enqueue multiple transaction categorization jobs

    Args:
        tx_ids: List of bank transaction IDs to process

    Returns:
        int: Number of successfully enqueued jobs
    """
    success_count = 0

    for tx_id in tx_ids:
        if enqueue_categorize(tx_id):
            success_count += 1

    logger.info(f"📊 Enqueued {success_count}/{len(tx_ids)} categorization jobs")
    return success_count

# CLI usage
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python enqueue_categorize.py <transaction_id>")
        print("   or: python enqueue_categorize.py <tx_id1> <tx_id2> <tx_id3>...")
        sys.exit(1)

    tx_ids = sys.argv[1:]

    if len(tx_ids) == 1:
        success = enqueue_categorize(tx_ids[0])
        if success:
            print(f"✅ Successfully enqueued job for transaction: {tx_ids[0]}")
        else:
            print(f"❌ Failed to enqueue job for transaction: {tx_ids[0]}")
    else:
        success_count = enqueue_bulk_categorize(tx_ids)
        print(f"📊 Successfully enqueued {success_count}/{len(tx_ids)} jobs")