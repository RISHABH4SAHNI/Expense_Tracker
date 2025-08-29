"""
Background worker for processing transaction categorization jobs
Simulates the LLM-powered transaction processing pipeline
"""
import asyncio
import json
import logging
import redis.asyncio as redis
from typing import Optional
import os
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CategoryWorker:
    """Worker class for processing categorization jobs from Redis queue"""

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client = None
        self.running = False

    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            logger.info("✅ Worker connected to Redis")
        except Exception as e:
            logger.error(f"❌ Worker failed to connect to Redis: {e}")
            raise

    async def categorize_transaction(self, transaction_id: str) -> bool:
        """
        Categorize a transaction using mock logic
        In production, this would call the LLM service
        """
        try:
            logger.info(f"🤖 Processing categorization for transaction: {transaction_id}")

            # Mock categorization logic (replace with actual LLM call)
            # Simulate processing time
            await asyncio.sleep(1)

            # Mock category assignment based on transaction ID pattern
            category_mapping = {
                "swiggy": "food",
                "uber": "transport", 
                "amazon": "shopping",
                "salary": "salary",
                "atm": "other"
            }

            # Simple mock logic - in reality this would analyze the raw_desc
            category = "other"  # default
            for keyword, cat in category_mapping.items():
                if keyword.lower() in transaction_id.lower():
                    category = cat
                    break

            # In production, you would update the database here
            logger.info(f"✅ Transaction {transaction_id} categorized as: {category}")

            # Add to completed jobs list for monitoring
            completed_job = {
                "transaction_id": transaction_id,
                "category": category,
                "processed_at": datetime.utcnow().isoformat(),
                "status": "completed"
            }

            await self.redis_client.lpush("completed_jobs", json.dumps(completed_job))
            return True

        except Exception as e:
            logger.error(f"❌ Failed to categorize transaction {transaction_id}: {e}")

            # Add to failed jobs list
            failed_job = {
                "transaction_id": transaction_id,
                "error": str(e),
                "failed_at": datetime.utcnow().isoformat(),
                "status": "failed"
            }

            await self.redis_client.lpush("failed_jobs", json.dumps(failed_job))
            return False

    async def process_job(self, job_data: dict) -> bool:
        """Process a single categorization job"""
        transaction_id = job_data.get("transaction_id")
        job_type = job_data.get("job_type")

        if job_type == "categorize_transaction":
            return await self.categorize_transaction(transaction_id)
        else:
            logger.warning(f"⚠️ Unknown job type: {job_type}")
            return False

    async def run_worker(self):
        """Main worker loop - processes jobs from Redis queue"""
        logger.info("🚀 Starting categorization worker...")
        self.running = True

        while self.running:
            try:
                # Block for up to 1 second waiting for jobs
                job_data = await self.redis_client.brpop("categorization_jobs", timeout=1)

                if job_data:
                    queue_name, job_payload = job_data
                    logger.info(f"📨 Received job from queue: {queue_name.decode()}")

                    try:
                        job = json.loads(job_payload.decode())
                        await self.process_job(job)
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
        logger.info("🛑 Stopping categorization worker...")
        self.running = False
        if self.redis_client:
            await self.redis_client.close()

    async def get_job_stats(self) -> dict:
        """Get statistics about job processing"""
        try:
            pending_count = await self.redis_client.llen("categorization_jobs")
            completed_count = await self.redis_client.llen("completed_jobs")
            failed_count = await self.redis_client.llen("failed_jobs")

            return {
                "pending_jobs": pending_count,
                "completed_jobs": completed_count,
                "failed_jobs": failed_count,
                "worker_status": "running" if self.running else "stopped"
            }
        except Exception as e:
            logger.error(f"❌ Failed to get job stats: {e}")
            return {"error": str(e)}

# CLI runner for the worker
async def main():
    """Run the worker as a standalone process"""
    worker = CategoryWorker()

    try:
        await worker.connect()
        await worker.run_worker()
    except KeyboardInterrupt:
        logger.info("⏹️ Received interrupt signal")
    finally:
        await worker.stop()

if __name__ == "__main__":
    asyncio.run(main())