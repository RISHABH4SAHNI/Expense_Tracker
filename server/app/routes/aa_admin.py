"""
AA Admin Routes

Administrative endpoints for managing AA sync workers and scheduler.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncpg
import logging

from app.database import get_db
from app.workers.aa_worker import enqueue_aa_sync, AAWorker
from app.scheduler.aa_scheduler import AAScheduler

logger = logging.getLogger(__name__)
router = APIRouter()

# Global instances (would be better managed in a proper service container)
_aa_worker_instance = None
_aa_scheduler_instance = None


@router.post("/admin/aa/enqueue-sync")
async def enqueue_sync_endpoint(
    user_id: str = Query(..., description="User ID"),
    account_id: str = Query(..., description="AA Account UUID"),
    since_days: int = Query(7, description="Sync transactions from N days ago"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Manually enqueue an AA sync job for testing
    """
    try:
        # Verify account exists
        account_row = await db.fetchrow("""
            SELECT id, user_id, aa_account_id, display_name
            FROM aa_accounts 
            WHERE id = $1 AND user_id = $2
        """, account_id, user_id)

        if not account_row:
            raise HTTPException(
                status_code=404, 
                detail=f"Account {account_id} not found for user {user_id}"
            )

        # Calculate since timestamp
        since_ts = datetime.utcnow() - timedelta(days=since_days)

        # Enqueue the job
        success = await enqueue_aa_sync(
            user_id=user_id,
            account_id=account_id,
            since_ts=since_ts
        )

        if success:
            return {
                "message": "AA sync job enqueued successfully",
                "account_id": account_id,
                "aa_account_id": account_row['aa_account_id'],
                "user_id": user_id,
                "since_ts": since_ts.isoformat(),
                "status": "queued"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to enqueue job")

    except Exception as e:
        logger.error(f"Failed to enqueue AA sync job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/aa/worker/stats")
async def get_worker_stats():
    """Get AA worker statistics"""
    try:
        # Create temporary worker instance to get stats
        worker = AAWorker()
        await worker.connect()

        stats = await worker.get_stats()
        await worker.stop()

        return {
            "message": "AA worker statistics",
            **stats
        }

    except Exception as e:
        logger.error(f"Failed to get worker stats: {e}")
        return {
            "error": str(e),
            "message": "Failed to get worker statistics"
        }


@router.get("/admin/aa/scheduler/stats")
async def get_scheduler_stats():
    """Get AA scheduler statistics"""
    try:
        scheduler = AAScheduler()
        await scheduler.connect()

        stats = await scheduler.get_scheduler_stats()
        await scheduler.redis_client.close()

        return {
            "message": "AA scheduler statistics",
            **stats
        }

    except Exception as e:
        logger.error(f"Failed to get scheduler stats: {e}")
        return {
            "error": str(e),
            "message": "Failed to get scheduler statistics"
        }


@router.post("/admin/aa/scheduler/trigger")
async def trigger_scheduler_run():
    """Manually trigger a scheduler run"""
    try:
        scheduler = AAScheduler()
        await scheduler.connect()

        result = await scheduler.schedule_account_syncs()
        await scheduler.redis_client.close()

        return {
            "message": "Scheduler run completed",
            **result
        }

    except Exception as e:
        logger.error(f"Failed to trigger scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/aa/queue/status")
async def get_queue_status():
    """Get status of all AA-related queues"""
    try:
        worker = AAWorker()
        await worker.connect()

        # Get queue sizes
        main_queue_size = await worker.redis_client.llen("aa_sync")
        retry_queue_size = await worker.redis_client.llen("aa_sync_retry")
        dlq_size = await worker.redis_client.llen("aa_dlq")
        completed_size = await worker.redis_client.llen("aa_sync_completed")
        failed_size = await worker.redis_client.llen("aa_sync_failed")

        await worker.stop()

        return {
            "message": "Queue status",
            "queues": {
                "main_queue": main_queue_size,
                "retry_queue": retry_queue_size,
                "dead_letter_queue": dlq_size,
                "completed_jobs": completed_size,
                "failed_jobs": failed_size
            },
            "total_pending": main_queue_size + retry_queue_size
        }

    except Exception as e:
        logger.error(f"Failed to get queue status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/aa/queue/clear")
async def clear_queues():
    """Clear all AA sync queues (for development/testing)"""
    try:
        worker = AAWorker()
        await worker.connect()

        # Clear all queues
        await worker.redis_client.delete("aa_sync")
        await worker.redis_client.delete("aa_sync_retry")
        await worker.redis_client.delete("aa_dlq")
        await worker.redis_client.delete("aa_sync_completed")
        await worker.redis_client.delete("aa_sync_failed")

        await worker.stop()

        logger.info("🧹 Cleared all AA sync queues")

        return {
            "message": "All AA sync queues cleared successfully"
        }

    except Exception as e:
        logger.error(f"Failed to clear queues: {e}")
        raise HTTPException(status_code=500, detail=str(e))