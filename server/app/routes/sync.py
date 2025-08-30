"""
Sync API Routes

Provides endpoints for testing and managing transaction sync operations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional, List
import asyncpg
import logging

from app.database import get_db
from app.services.sync import (
    sync_account,
    sync_all_user_accounts,
    normalize_tx_id,
    upsert_transaction
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/sync/account/{account_id}")
async def sync_account_endpoint(
    account_id: str,
    user_id: str = Query(..., description="User ID"),
    since_days: int = Query(7, description="Sync transactions from N days ago"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Sync transactions for a specific AA account.

    This endpoint demonstrates idempotent sync - running it multiple times
    will only insert new transactions, skipping duplicates.
    """
    try:
        # Get account info from database
        account_row = await db.fetchrow("""
            SELECT id, user_id, aa_account_id, display_name
            FROM aa_accounts 
            WHERE aa_account_id = $1 AND user_id = $2
        """, account_id, user_id)

        if not account_row:
            raise HTTPException(
                status_code=404, 
                detail=f"Account {account_id} not found for user {user_id}"
            )

        # Calculate since timestamp
        since_ts = datetime.utcnow() - timedelta(days=since_days)

        # Perform sync
        result = await sync_account(dict(account_row), since_ts, db)

        return {
            "message": "Account sync completed",
            "account_id": account_id,
            "since_days": since_days,
            **result
        }

    except Exception as e:
        logger.error(f"Sync failed for account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/user/{user_id}")
async def sync_user_accounts_endpoint(
    user_id: str,
    since_days: int = Query(7, description="Sync transactions from N days ago"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Sync transactions for all AA accounts belonging to a user.

    Demonstrates bulk idempotent sync across multiple accounts.
    """
    try:
        # Calculate since timestamp
        since_ts = datetime.utcnow() - timedelta(days=since_days)

        # Perform sync for all user accounts
        results = await sync_all_user_accounts(user_id, since_ts, db)

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"No AA accounts found for user {user_id}"
            )

        # Calculate totals
        total_inserted = sum(r.get("inserted_count", 0) for r in results)
        total_skipped = sum(r.get("skipped_count", 0) for r in results)
        total_errors = sum(r.get("error_count", 0) for r in results)

        return {
            "message": "User sync completed",
            "user_id": user_id,
            "since_days": since_days,
            "accounts_synced": len(results),
            "total_inserted": total_inserted,
            "total_skipped": total_skipped,
            "total_errors": total_errors,
            "account_results": results
        }

    except Exception as e:
        logger.error(f"Sync failed for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/test/normalize")
async def test_normalize_endpoint():
    """Test endpoint to demonstrate transaction hash normalization."""

    sample_transactions = [
        {
            "id": "tx_001",
            "user_id": "user_123",
            "account_id": "acc_456",
            "amount": 150.00,
            "ts": "2024-01-15T10:30:00+05:30"
        },
        {
            "id": "tx_001",  # Same transaction
            "user_id": "user_123",
            "account_id": "acc_456", 
            "amount": 150.00,
            "ts": "2024-01-15T10:30:00+05:30"
        },
        {
            "id": "tx_001",  # Different amount = different hash
            "user_id": "user_123",
            "account_id": "acc_456",
            "amount": 150.01,
            "ts": "2024-01-15T10:30:00+05:30"
        }
    ]

    results = []
    for i, tx in enumerate(sample_transactions):
        hash_value = normalize_tx_id(tx)
        results.append({
            "transaction_index": i,
            "transaction": tx,
            "normalized_hash": hash_value
        })

    return {
        "message": "Transaction hash normalization demo",
        "note": "Same transaction data produces same hash (for deduplication)",
        "results": results
    }