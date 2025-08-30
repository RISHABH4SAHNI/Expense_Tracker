"""
Account Aggregator Sync Worker

Background worker for processing AA sync jobs with retries and dead letter queue:
- Listens to "aa_sync" Redis queue
- Processes jobs with payload: {user_id, account_id, since_ts}
- Calls sync.sync_account() and logs to AASyncLog
- Implements exponential backoff retry strategy
- Dead letter queue for failed jobs after max retries
- CLI helper for local development
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

import asyncpg
import redis.asyncio as redis

from app.services.sync import sync_account
from app.database import get_db, db_pool
from app.models.aa_models import AASyncStatus

logger = logging.getLogger(__name__)

@dataclass
class AAJobPayload:
    """Data structure for AA sync job payload"""
    user_id: str
    account_id: str  # This is the UUID from aa_accounts table
    since_ts: Optional[str] = None  # ISO timestamp string
    retry_count: int = 0
    original_enqueue_time: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AAJobPayload':
        """Create payload from dictionary"""
        return cls(
            user_id=data['user_id'],
            account_id=data['account_id'],
            since_ts=data.get('since_ts'),
            retry_count=data.get('retry_count', 0),
            original_enqueue_time=data.get('original_enqueue_time')
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert payload to dictionary"""
        return {
            'user_id': self.user_id,
            'account_id': self.account_id,
            'since_ts': self.since_ts,
            'retry_count': self.retry_count,
            'original_enqueue_time': self.original_enqueue_time
        }


class AAWorker:
    """Worker for processing Account Aggregator sync jobs"""

    def __init__(self, redis_url: str = None, max_retries: int = 3):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client = None
        self.running = False
        self.max_retries = max_retries
        self.retry_delays = [30, 120, 300]  # 30s, 2m, 5m

        # Queue names
        self.main_queue = "aa_sync"
        self.retry_queue = "aa_sync_retry"
        self.dlq = "aa_dlq"

    async def connect(self):
        """Connect to Redis and database"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            logger.info("✅ AA Worker connected to Redis")
        except Exception as e:
            logger.error(f"❌ AA Worker failed to connect to Redis: {e}")
            raise

    async def get_account_info(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get account information from database"""
        try:
            if not db_pool:
                logger.error("Database pool not available")
                return None

            async with db_pool.acquire() as conn:
                account_row = await conn.fetchrow("""
                    SELECT id, user_id, aa_account_id, display_name
                    FROM aa_accounts 
                    WHERE id = $1
                """, account_id)

                if account_row:
                    return dict(account_row)
                else:
                    logger.error(f"Account {account_id} not found in database")
                    return None

        except Exception as e:
            logger.error(f"Failed to get account info for {account_id}: {e}")
            return None

    async def process_sync_job(self, payload: AAJobPayload) -> bool:
        """
        Process a single AA sync job

        Returns:
            bool: True if successful, False if failed
        """
        start_time = datetime.utcnow()

        try:
            logger.info(f"🔄 Processing AA sync job for account {payload.account_id} (attempt {payload.retry_count + 1})")

            # Get account information
            account_info = await self.get_account_info(payload.account_id)
            if not account_info:
                logger.error(f"Cannot process job - account {payload.account_id} not found")
                return False

            # Parse since timestamp
            since_ts = None
            if payload.since_ts:
                try:
                    since_ts = datetime.fromisoformat(payload.since_ts.replace('Z', '+00:00'))
                except ValueError:
                    logger.warning(f"Invalid since_ts format: {payload.since_ts}, using None")

            # Perform the sync
            if not db_pool:
                logger.error("Database pool not available")
                return False

            async with db_pool.acquire() as conn:
                result = await sync_account(account_info, since_ts, conn)

            # Check if sync was successful
            if result.get('status') == 'completed':
                logger.info(f"✅ AA sync completed for account {payload.account_id}: "
                          f"{result.get('inserted_count', 0)} inserted, "
                          f"{result.get('skipped_count', 0)} skipped")

                # Log successful job completion
                await self._log_job_completion(payload, result, True)
                return True
            else:
                error_msg = result.get('error', 'Unknown sync error')
                logger.error(f"❌ AA sync failed for account {payload.account_id}: {error_msg}")
                await self._log_job_completion(payload, result, False)
                return False

        except Exception as e:
            logger.error(f"❌ Exception in AA sync job for account {payload.account_id}: {e}")
            await self._log_job_completion(payload, {"error": str(e)}, False)
            return False

    async def _log_job_completion(self, payload: AAJobPayload, result: Dict[str, Any], success: bool):
        """Log job completion to Redis for monitoring"""
        try:
            log_entry = {
                "job_type": "aa_sync",
                "account_id": payload.account_id,
                "user_id": payload.user_id,
                "success": success,
                "result": result,
                "retry_count": payload.retry_count,
                "completed_at": datetime.utcnow().isoformat(),
                "original_enqueue_time": payload.original_enqueue_time
            }

            queue_name = "aa_sync_completed" if success else "aa_sync_failed"
            await self.redis_client.lpush(queue_name, json.dumps(log_entry))

            # Keep only last 100 entries
            await self.redis_client.ltrim(queue_name, 0, 99)

        except Exception as e:
            logger.error(f"Failed to log job completion: {e}")

    async def handle_job_retry(self, payload: AAJobPayload):
        """Handle job retry with exponential backoff"""
        if payload.retry_count >= self.max_retries:
            # Send to dead letter queue
            logger.warning(f"⚠️ Job for account {payload.account_id} exceeded max retries, sending to DLQ")

            dlq_entry = {
                **payload.to_dict(),
                "failed_at": datetime.utcnow().isoformat(),
                "reason": "max_retries_exceeded"
            }

            await self.redis_client.lpush(self.dlq, json.dumps(dlq_entry))
            return

        # Schedule retry with delay
        retry_delay = self.retry_delays[min(payload.retry_count, len(self.retry_delays) - 1)]
        retry_time = datetime.utcnow() + timedelta(seconds=retry_delay)

        logger.info(f"🔄 Scheduling retry for account {payload.account_id} in {retry_delay}s (attempt {payload.retry_count + 2})")

        # Increment retry count
        payload.retry_count += 1

        # Add to retry queue with timestamp
        retry_entry = {
            **payload.to_dict(),
            "retry_at": retry_time.isoformat()
        }

        await self.redis_client.lpush(self.retry_queue, json.dumps(retry_entry))

    async def process_retry_queue(self):
        """Process jobs in retry queue that are ready"""
        try:
            # Get all items from retry queue
            retry_items = await self.redis_client.lrange(self.retry_queue, 0, -1)

            now = datetime.utcnow()
            requeued_count = 0

            for item in retry_items:
                try:
                    retry_data = json.loads(item.decode())
                    retry_time = datetime.fromisoformat(retry_data['retry_at'].replace('Z', '+00:00'))

                    if now >= retry_time:
                        # Remove from retry queue
                        await self.redis_client.lrem(self.retry_queue, 1, item)

                        # Remove retry_at field and add back to main queue
                        retry_data.pop('retry_at', None)
                        await self.redis_client.lpush(self.main_queue, json.dumps(retry_data))
                        requeued_count += 1

                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    logger.error(f"Invalid retry queue item: {e}")
                    # Remove invalid item
                    await self.redis_client.lrem(self.retry_queue, 1, item)

            if requeued_count > 0:
                logger.info(f"📤 Requeued {requeued_count} jobs from retry queue")

        except Exception as e:
            logger.error(f"Error processing retry queue: {e}")

    async def run_worker(self):
        """Main worker loop"""
        logger.info("🚀 Starting AA sync worker...")
        self.running = True

        while self.running:
            try:
                # Process retry queue first
                await self.process_retry_queue()

                # Wait for jobs from main queue
                job_data = await self.redis_client.brpop(self.main_queue, timeout=5)

                if job_data:
                    queue_name, job_payload = job_data
                    logger.debug(f"📨 Received job from queue: {queue_name.decode()}")

                    try:
                        job_dict = json.loads(job_payload.decode())
                        payload = AAJobPayload.from_dict(job_dict)

                        # Set original enqueue time if not set
                        if not payload.original_enqueue_time:
                            payload.original_enqueue_time = datetime.utcnow().isoformat()

                        # Process the job
                        success = await self.process_sync_job(payload)

                        if not success:
                            # Handle retry
                            await self.handle_job_retry(payload)

                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Invalid job payload: {e}")
                    except Exception as e:
                        logger.error(f"❌ Job processing failed: {e}")

            except asyncio.CancelledError:
                logger.info("🛑 Worker cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Worker error: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def stop(self):
        """Stop the worker"""
        logger.info("🛑 Stopping AA sync worker...")
        self.running = False
        if self.redis_client:
            await self.redis_client.close()

    async def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics"""
        try:
            stats = {
                "main_queue_size": await self.redis_client.llen(self.main_queue),
                "retry_queue_size": await self.redis_client.llen(self.retry_queue),
                "dlq_size": await self.redis_client.llen(self.dlq),
                "completed_jobs": await self.redis_client.llen("aa_sync_completed"),
                "failed_jobs": await self.redis_client.llen("aa_sync_failed"),
                "worker_status": "running" if self.running else "stopped"
            }
            return stats
        except Exception as e:
            logger.error(f"Failed to get worker stats: {e}")
            return {"error": str(e)}


# Helper function to enqueue AA sync jobs
async def enqueue_aa_sync(
    user_id: str, 
    account_id: str, 
    since_ts: Optional[datetime] = None,
    redis_client: Optional[redis.Redis] = None
) -> bool:
    """
    Enqueue an AA sync job

    Args:
        user_id: User identifier
        account_id: AA account UUID (from aa_accounts table)
        since_ts: Sync transactions since this timestamp
        redis_client: Redis client (will create if not provided)

    Returns:
        bool: True if successfully enqueued
    """
    try:
        # Use provided client or create new one
        if redis_client is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            redis_client = redis.from_url(redis_url)
            should_close = True
        else:
            should_close = False

        payload = AAJobPayload(
            user_id=user_id,
            account_id=account_id,
            since_ts=since_ts.isoformat() if since_ts else None,
            original_enqueue_time=datetime.utcnow().isoformat()
        )

        await redis_client.lpush("aa_sync", json.dumps(payload.to_dict()))

        logger.info(f"📤 Enqueued AA sync job for account {account_id}")

        if should_close:
            await redis_client.close()

        return True

    except Exception as e:
        logger.error(f"Failed to enqueue AA sync job: {e}")
        return False


# CLI runner for development
async def main():
    """Run the AA worker as a standalone process"""
    worker = AAWorker()

    try:
        await worker.connect()
        await worker.run_worker()
    except KeyboardInterrupt:
        logger.info("⏹️ Received interrupt signal")
    finally:
        await worker.stop()

if __name__ == "__main__":
    # Configure logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("🚀 Starting AA Sync Worker...")
    print("Press Ctrl+C to stop")

    asyncio.run(main())