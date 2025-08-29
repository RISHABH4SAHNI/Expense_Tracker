"""
Job monitoring routes for tracking background processing
"""
from fastapi import APIRouter, Depends, HTTPException
import redis.asyncio as redis
import json
import logging
from typing import Dict, List
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Get Redis client from transactions module
def get_redis_client():
    from app.routes.transactions import redis_client
    return redis_client

@router.get("/stats")
async def get_job_stats():
    """Get statistics about job processing"""
    redis_client = get_redis_client()

    if not redis_client:
        return {
            "error": "Redis not available",
            "pending_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "worker_status": "unavailable"
        }

    try:
        pending_count = await redis_client.llen("categorization_jobs")
        completed_count = await redis_client.llen("completed_jobs")  
        failed_count = await redis_client.llen("failed_jobs")

        return {
            "pending_jobs": pending_count,
            "completed_jobs": completed_count,
            "failed_jobs": failed_count,
            "worker_status": "available",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Failed to get job stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job stats: {str(e)}")

@router.get("/recent")
async def get_recent_jobs(limit: int = 10):
    """Get recent completed and failed jobs"""
    redis_client = get_redis_client()

    if not redis_client:
        return {"error": "Redis not available", "completed": [], "failed": []}

    try:
        # Get recent completed jobs
        completed_raw = await redis_client.lrange("completed_jobs", 0, limit - 1)
        completed = []
        for job_raw in completed_raw:
            try:
                job = json.loads(job_raw.decode())
                completed.append(job)
            except json.JSONDecodeError:
                continue

        # Get recent failed jobs
        failed_raw = await redis_client.lrange("failed_jobs", 0, limit - 1)
        failed = []
        for job_raw in failed_raw:
            try:
                job = json.loads(job_raw.decode())
                failed.append(job)
            except json.JSONDecodeError:
                continue

        return {
            "completed": completed,
            "failed": failed,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Failed to get recent jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recent jobs: {str(e)}")

@router.post("/clear")
async def clear_job_queues():
    """Clear all job queues (for development/testing)"""
    redis_client = get_redis_client()

    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis not available")

    try:
        # Clear all job queues
        await redis_client.delete("categorization_jobs")
        await redis_client.delete("completed_jobs")
        await redis_client.delete("failed_jobs")

        logger.info("🧹 Cleared all job queues")
        return {
            "message": "All job queues cleared successfully",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Failed to clear job queues: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear job queues: {str(e)}")