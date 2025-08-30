"""
Account Aggregator Sync Scheduler

Periodically schedules AA sync jobs for linked accounts:
- Runs on configurable intervals (default: every 4 hours)
- Finds accounts that need syncing based on last_sync_at
- Enqueues aa_sync jobs for stale accounts
- Supports both APScheduler and simple cron-like loop
- Environment flag to disable in local development
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import asyncpg
import redis.asyncio as redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import db_pool
from app.workers.aa_worker import enqueue_aa_sync

logger = logging.getLogger(__name__)


class AAScheduler:
    """Scheduler for automatic AA account synchronization"""

    def __init__(self):
        self.scheduler = None
        self.redis_client = None
        self.running = False

        # Configuration from environment
        self.enabled = os.getenv("AA_SCHEDULER_ENABLED", "true").lower() == "true"
        self.sync_interval_hours = int(os.getenv("AA_SYNC_INTERVAL_HOURS", "4"))
        self.sync_poll_interval = int(os.getenv("SYNC_POLL_INTERVAL", str(self.sync_interval_hours * 3600)))  # seconds
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        # Only sync accounts that haven't been synced in this many hours
        self.stale_threshold_hours = int(os.getenv("AA_STALE_THRESHOLD_HOURS", str(self.sync_interval_hours)))

        logger.info(f"AA Scheduler configured: enabled={self.enabled}, interval={self.sync_interval_hours}h")

    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            logger.info("✅ AA Scheduler connected to Redis")
        except Exception as e:
            logger.error(f"❌ AA Scheduler failed to connect to Redis: {e}")
            raise

    async def get_stale_accounts(self) -> List[Dict[str, Any]]:
        """
        Get accounts that need syncing based on last_sync_at timestamp

        Returns:
            List of account dictionaries that need syncing
        """
        if not db_pool:
            logger.error("Database pool not available")
            return []

        try:
            stale_threshold = datetime.utcnow() - timedelta(hours=self.stale_threshold_hours)

            async with db_pool.acquire() as conn:
                # Get accounts that haven't been synced recently or never synced
                accounts = await conn.fetch("""
                    SELECT 
                        aa.id,
                        aa.user_id,
                        aa.aa_account_id,
                        aa.display_name,
                        aa.last_sync_at,
                        aa.created_at
                    FROM aa_accounts aa
                    INNER JOIN aa_consents ac ON aa.user_id = ac.user_id
                    WHERE ac.status = 'active'
                    AND (
                        aa.last_sync_at IS NULL 
                        OR aa.last_sync_at < $1
                    )
                    ORDER BY 
                        aa.last_sync_at ASC NULLS FIRST,
                        aa.created_at ASC
                """, stale_threshold)

                stale_accounts = [dict(account) for account in accounts]

                if stale_accounts:
                    logger.info(f"Found {len(stale_accounts)} accounts needing sync (stale threshold: {stale_threshold})")
                    for account in stale_accounts:
                        last_sync = account['last_sync_at']
                        last_sync_str = last_sync.strftime('%Y-%m-%d %H:%M:%S') if last_sync else 'Never'
                        logger.debug(f"  - {account['aa_account_id']} ({account['display_name']}) - Last sync: {last_sync_str}")
                else:
                    logger.debug("No stale accounts found")

                return stale_accounts

        except Exception as e:
            logger.error(f"Failed to get stale accounts: {e}")
            return []

    async def schedule_account_syncs(self) -> Dict[str, Any]:
        """
        Schedule sync jobs for stale accounts

        Returns:
            Dict with scheduling results
        """
        try:
            stale_accounts = await self.get_stale_accounts()

            if not stale_accounts:
                return {
                    "scheduled_count": 0,
                    "skipped_count": 0,
                    "error_count": 0,
                    "message": "No accounts need syncing"
                }

            scheduled_count = 0
            error_count = 0

            # Calculate since_ts for sync (sync last 7 days by default)
            since_ts = datetime.utcnow() - timedelta(days=7)

            for account in stale_accounts:
                try:
                    # Use last_sync_at if available, otherwise use since_ts
                    sync_since = account['last_sync_at'] or since_ts

                    success = await enqueue_aa_sync(
                        user_id=str(account['user_id']),
                        account_id=str(account['id']),
                        since_ts=sync_since,
                        redis_client=self.redis_client
                    )

                    if success:
                        scheduled_count += 1
                        logger.debug(f"📅 Scheduled sync for {account['aa_account_id']}")
                    else:
                        error_count += 1
                        logger.error(f"Failed to schedule sync for {account['aa_account_id']}")

                except Exception as e:
                    error_count += 1
                    logger.error(f"Error scheduling sync for {account['aa_account_id']}: {e}")

            result = {
                "scheduled_count": scheduled_count,
                "skipped_count": 0,
                "error_count": error_count,
                "total_accounts": len(stale_accounts),
                "timestamp": datetime.utcnow().isoformat()
            }

            if scheduled_count > 0:
                logger.info(f"📅 Scheduled {scheduled_count} AA sync jobs")

                # Log scheduling event to Redis
                await self.redis_client.lpush("aa_scheduler_events", json.dumps(result))
                await self.redis_client.ltrim("aa_scheduler_events", 0, 99)  # Keep last 100 events

            return result

        except Exception as e:
            logger.error(f"Failed to schedule account syncs: {e}")
            return {
                "scheduled_count": 0,
                "skipped_count": 0,
                "error_count": 1,
                "error": str(e)
            }

    async def run_scheduler_job(self):
        """Job function called by the scheduler"""
        logger.info("⏰ Running scheduled AA sync check...")

        try:
            result = await self.schedule_account_syncs()

            if result['scheduled_count'] > 0:
                logger.info(f"✅ Scheduled {result['scheduled_count']} sync jobs")
            else:
                logger.debug("ℹ️ No sync jobs needed at this time")

        except Exception as e:
            logger.error(f"❌ Scheduler job failed: {e}")

    async def start_scheduler(self):
        """Start the APScheduler-based scheduler"""
        if not self.enabled:
            logger.info("AA Scheduler is disabled (AA_SCHEDULER_ENABLED=false)")
            return

        logger.info(f"🚀 Starting AA Scheduler (interval: {self.sync_interval_hours}h)")

        try:
            await self.connect()

            self.scheduler = AsyncIOScheduler()

            # Add the recurring job
            self.scheduler.add_job(
                self.run_scheduler_job,
                trigger=IntervalTrigger(hours=self.sync_interval_hours),
                id='aa_sync_scheduler',
                name='Account Aggregator Sync Scheduler',
                replace_existing=True
            )

            self.scheduler.start()
            self.running = True

            logger.info(f"✅ AA Scheduler started successfully")

            # Run initial sync check
            await self.run_scheduler_job()

        except Exception as e:
            logger.error(f"❌ Failed to start AA Scheduler: {e}")
            raise

    async def stop_scheduler(self):
        """Stop the scheduler"""
        logger.info("🛑 Stopping AA Scheduler...")

        self.running = False

        if self.scheduler:
            self.scheduler.shutdown(wait=False)

        if self.redis_client:
            await self.redis_client.close()

        logger.info("✅ AA Scheduler stopped")

    async def get_scheduler_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        try:
            stale_accounts = await self.get_stale_accounts()

            stats = {
                "enabled": self.enabled,
                "running": self.running,
                "sync_interval_hours": self.sync_interval_hours,
                "stale_threshold_hours": self.stale_threshold_hours,
                "accounts_needing_sync": len(stale_accounts),
                "next_run": "N/A"  # APScheduler doesn't easily expose next run time
            }

            if self.scheduler and self.running:
                job = self.scheduler.get_job('aa_sync_scheduler')
                if job and job.next_run_time:
                    stats["next_run"] = job.next_run_time.isoformat()

            return stats

        except Exception as e:
            logger.error(f"Failed to get scheduler stats: {e}")
            return {"error": str(e)}


# Simple cron-like scheduler for development (no APScheduler dependency)
async def simple_scheduler_loop():
    """Simple scheduler loop for development/testing"""
    scheduler = AAScheduler()

    if not scheduler.enabled:
        logger.info("AA Scheduler is disabled")
        return

    try:
        await scheduler.connect()

        logger.info(f"🚀 Starting simple AA scheduler loop (interval: {scheduler.sync_interval_hours}h)")

        while True:
            try:
                await scheduler.run_scheduler_job()

                # Wait for next interval
                sleep_seconds = scheduler.sync_interval_hours * 3600
                logger.info(f"😴 Sleeping for {scheduler.sync_interval_hours}h until next sync check...")
                await asyncio.sleep(sleep_seconds)

            except asyncio.CancelledError:
                logger.info("🛑 Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in scheduler loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying

    finally:
        if scheduler.redis_client:
            await scheduler.redis_client.close()


# CLI runner for development
async def main():
    """Run the scheduler as a standalone process"""
    print("🕒 Starting AA Sync Scheduler...")
    print("Set AA_SCHEDULER_ENABLED=false to disable")
    print("Set AA_SYNC_INTERVAL_HOURS=N to change interval (default: 4)")
    print("Press Ctrl+C to stop")

    try:
        # Use simple scheduler for CLI mode
        await simple_scheduler_loop()
    except KeyboardInterrupt:
        logger.info("⏹️ Received interrupt signal")


if __name__ == "__main__":
    # Configure logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(main())