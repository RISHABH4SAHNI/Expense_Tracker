"""
Account Aggregator (AA) routes for Expense Tracker API

Handles AA consent flow, webhooks, transaction sync, and account management.
Provides endpoints for the complete AA integration workflow from consent to transaction sync.
"""

import json
import uuid
import logging
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from decimal import Decimal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from app.database import get_db
from app.deps.auth import get_current_user, AuthenticatedUser
from app.config import AA_MOCK_WEBHOOK_SECRET
from app.services.aa_client import aa_client
from app.models.aa_models import (
    ConsentStartOut, ConsentStatusOut, AAAccountOut, AASyncLogOut,
    AAConsentStatus, AASyncStatus
)
from app.models.pydantic_models import TransactionType

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aa", tags=["Account Aggregator"])


# Helper function to enqueue categorization jobs
async def enqueue_categorize_job(tx_id: str) -> bool:
    """
    Enqueue transaction categorization job

    Args:
        tx_id: Transaction ID to categorize

    Returns:
        bool: True if successfully enqueued
    """
    try:
        from app.utils.enqueue_categorize import enqueue_categorize
        return enqueue_categorize(tx_id)
    except Exception as e:
        logger.error(f"Failed to enqueue categorization job for {tx_id}: {e}")
        return False


@router.post("/consent/start", response_model=ConsentStartOut)
async def start_consent(
    user: AuthenticatedUser = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
) -> ConsentStartOut:
    """
    Start the Account Aggregator consent flow for a user

    Creates a new consent request and returns the consent URL and reference ID.
    The user needs to visit the consent URL to authorize account linking.

    Returns:
        ConsentStartOut: Consent details including URL and reference ID

    Raises:
        HTTPException: 500 if consent creation fails
    """
    try:
        logger.info(f"Starting AA consent flow for user: {user.id}")

        # Call AA client to start consent
        consent_data = await aa_client.start_consent(user.id)

        # Fetch the created consent from database
        consent_row = await db.fetchrow("""
            SELECT id, ref_id, status, created_at
            FROM aa_consents 
            WHERE user_id = $1 AND ref_id = $2
            ORDER BY created_at DESC 
            LIMIT 1
        """, user.id, consent_data["ref_id"])

        if not consent_row:
            raise HTTPException(
                status_code=500, 
                detail="Failed to create consent record"
            )

        # Return structured response
        return ConsentStartOut(
            consent_id=consent_row["id"],
            ref_id=consent_row["ref_id"],
            status=AAConsentStatus(consent_row["status"]),
            consent_url=consent_data.get("consent_url"),
            created_at=consent_row["created_at"]
        )

    except Exception as e:
        logger.error(f"Consent start failed for user {user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start consent flow: {str(e)}"
        )


@router.get("/consent/status", response_model=ConsentStatusOut)
async def get_consent_status(
    ref_id: str = Query(..., description="AA consent reference ID"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
) -> ConsentStatusOut:
    """
    Get the current status of an AA consent request

    Polls the AA client for the latest consent status and updates the database.
    Returns consent status and linked account information if available.

    Args:
        ref_id: AA consent reference ID

    Returns:
        ConsentStatusOut: Current consent status and metadata

    Raises:
        HTTPException: 404 if consent not found, 403 if not owned by user
    """
    try:
        # Verify consent belongs to user
        consent_row = await db.fetchrow("""
            SELECT id, ref_id, status, created_at, updated_at, last_polled_at
            FROM aa_consents 
            WHERE user_id = $1 AND ref_id = $2
        """, user.id, ref_id)

        if not consent_row:
            raise HTTPException(
                status_code=404,
                detail="Consent not found or not owned by user"
            )

        # Poll AA client for latest status
        current_status = await aa_client.poll_consent_status(ref_id)

        # Update database with latest status
        updated_row = await db.fetchrow("""
            UPDATE aa_consents 
            SET status = $1, last_polled_at = $2, updated_at = $2
            WHERE id = $3
            RETURNING id, ref_id, status, created_at, updated_at, last_polled_at
        """, current_status, datetime.utcnow(), consent_row["id"])

        logger.info(f"Consent {ref_id} status: {current_status}")

        return ConsentStatusOut(
            consent_id=updated_row["id"],
            ref_id=updated_row["ref_id"],
            status=AAConsentStatus(updated_row["status"]),
            created_at=updated_row["created_at"],
            updated_at=updated_row["updated_at"],
            last_polled_at=updated_row["last_polled_at"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Consent status check failed for {ref_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check consent status: {str(e)}"
        )


@router.post("/webhook")
async def aa_webhook(
    request: Request,
    db: asyncpg.Connection = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Public webhook endpoint for Account Aggregator notifications

    Receives transaction data from AA providers and processes them idempotently.
    Verifies webhook signature for security and logs all webhook activities.

    Expected payload format:
    {
        "account_id": "string",
        "transaction": {
            "id": "string",
            "ts": "2023-12-01T10:00:00Z",
            "amount": 100.50,
            "type": "debit",
            "raw_desc": "Transaction description"
        }
    }

    Returns:
        dict: Success/error status with processing details
    """
    try:
        # Get request body and headers
        body = await request.body()
        signature = request.headers.get("X-AA-Signature", "")

        # Verify webhook signature
        if not _verify_webhook_signature(body, signature):
            logger.warning(f"Invalid webhook signature from {request.client.host}")
            raise HTTPException(
                status_code=401,
                detail="Invalid webhook signature"
            )

        # Parse webhook payload
        try:
            payload = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON payload"
            )

        # Validate required fields
        account_id = payload.get("account_id")
        transaction_data = payload.get("transaction", {})

        if not account_id or not transaction_data:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: account_id or transaction"
            )

        # Find the user who owns this AA account
        account_row = await db.fetchrow("""
            SELECT user_id, display_name 
            FROM aa_accounts 
            WHERE aa_account_id = $1
        """, account_id)

        if not account_row:
            logger.warning(f"Webhook for unknown account: {account_id}")
            return {"status": "ignored", "reason": "unknown_account"}

        user_id = str(account_row["user_id"])

        # Extract transaction details
        tx_id = transaction_data.get("id")
        tx_ts = transaction_data.get("ts")
        tx_amount = transaction_data.get("amount")
        tx_type = transaction_data.get("type")
        tx_desc = transaction_data.get("raw_desc", "")

        if not all([tx_id, tx_ts, tx_amount, tx_type]):
            raise HTTPException(
                status_code=400,
                detail="Missing required transaction fields"
            )

        # Parse timestamp
        if isinstance(tx_ts, str):
            tx_timestamp = datetime.fromisoformat(tx_ts.replace('Z', '+00:00'))
        else:
            tx_timestamp = datetime.utcnow()

        # Insert transaction idempotently
        existing_tx = await db.fetchval("""
            SELECT id FROM transactions 
            WHERE bank_transaction_id = $1
        """, tx_id)

        if existing_tx:
            logger.info(f"Transaction {tx_id} already exists, skipping")
            return {"status": "duplicate", "transaction_id": tx_id}

        # Insert new transaction
        new_tx_id = await db.fetchval("""
            INSERT INTO transactions (
                bank_transaction_id, user_id, ts, amount, type, 
                raw_desc, account_id, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8)
            RETURNING id
        """, 
            tx_id, user_id, tx_timestamp, Decimal(str(tx_amount)),
            tx_type, tx_desc, account_id, datetime.utcnow()
        )

        # Log webhook processing
        await db.execute("""
            INSERT INTO aa_sync_logs (
                user_id, start_ts, end_ts, status, inserted_count, created_at
            ) VALUES ($1, $2, $2, $3, 1, $2)
        """, user_id, datetime.utcnow(), AASyncStatus.COMPLETED)

        # Enqueue categorization job in background
        background_tasks.add_task(enqueue_categorize_job, str(new_tx_id))

        logger.info(f"Webhook processed: {tx_id} for account {account_id}")

        return {
            "status": "success",
            "transaction_id": tx_id,
            "internal_id": str(new_tx_id),
            "processed_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Webhook processing failed"
        )


@router.post("/sync")
async def sync_transactions(
    user: AuthenticatedUser = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict[str, Any]:
    """
    Manually trigger transaction sync for user's linked AA accounts

    Fetches transactions from all linked AA accounts since last sync.
    Inserts new transactions idempotently and enqueues categorization jobs.
    Creates comprehensive sync logs for monitoring and debugging.

    Returns:
        dict: Sync results with counts and status for each account

    Raises:
        HTTPException: 404 if no linked accounts, 500 if sync fails
    """
    sync_start = datetime.utcnow()
    total_inserted = 0
    results = []

    try:
        # Get user's linked AA accounts
        accounts = await db.fetch("""
            SELECT id, aa_account_id, display_name, last_sync_at
            FROM aa_accounts 
            WHERE user_id = $1
            ORDER BY created_at DESC
        """, user.id)

        if not accounts:
            raise HTTPException(
                status_code=404,
                detail="No linked AA accounts found"
            )

        logger.info(f"Starting sync for user {user.id}, {len(accounts)} accounts")

        # Process each account
        for account in accounts:
            account_id = account["aa_account_id"]
            last_sync = account["last_sync_at"] or (datetime.utcnow() - timedelta(days=30))

            # Create sync log entry
            sync_log_id = await db.fetchval("""
                INSERT INTO aa_sync_logs (
                    user_id, account_id, start_ts, status, created_at
                ) VALUES ($1, $2, $3, $4, $3)
                RETURNING id
            """, user.id, account["id"], sync_start, AASyncStatus.RUNNING)

            try:
                # Fetch transactions from AA client
                transactions = await aa_client.fetch_transactions(
                    account_id=account_id,
                    since_ts=last_sync,
                    limit=500
                )

                inserted_count = 0
                duplicate_count = 0

                # Process each transaction
                for tx in transactions:
                    # Check if transaction already exists
                    existing = await db.fetchval("""
                        SELECT id FROM transactions 
                        WHERE bank_transaction_id = $1
                    """, tx["id"])

                    if existing:
                        duplicate_count += 1
                        continue

                    # Insert new transaction
                    new_tx_id = await db.fetchval("""
                        INSERT INTO transactions (
                            bank_transaction_id, user_id, ts, amount, type,
                            raw_desc, account_id, created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8)
                        RETURNING id
                    """,
                        tx["id"], user.id, tx["ts"], Decimal(str(tx["amount"])),
                        tx["type"], tx["raw_desc"], account_id, datetime.utcnow()
                    )

                    # Enqueue categorization job
                    background_tasks.add_task(enqueue_categorize_job, str(new_tx_id))
                    inserted_count += 1

                # Update account last sync timestamp
                await db.execute("""
                    UPDATE aa_accounts 
                    SET last_sync_at = $1, updated_at = $1
                    WHERE id = $2
                """, sync_start, account["id"])

                # Mark sync log as completed
                await db.execute("""
                    UPDATE aa_sync_logs 
                    SET end_ts = $1, status = $2, inserted_count = $3, updated_at = $1
                    WHERE id = $4
                """, datetime.utcnow(), AASyncStatus.COMPLETED, inserted_count, sync_log_id)

                total_inserted += inserted_count

                results.append({
                    "account_id": account_id,
                    "display_name": account["display_name"],
                    "status": "success",
                    "inserted_count": inserted_count,
                    "duplicate_count": duplicate_count,
                    "total_fetched": len(transactions)
                })

                logger.info(f"Account {account_id}: {inserted_count} new, {duplicate_count} duplicates")

            except Exception as e:
                error_msg = f"Sync failed for account {account_id}: {str(e)}"
                logger.error(error_msg)

                # Mark sync log as failed
                await db.execute("""
                    UPDATE aa_sync_logs 
                    SET end_ts = $1, status = $2, error_text = $3, updated_at = $1
                    WHERE id = $4
                """, datetime.utcnow(), AASyncStatus.FAILED, error_msg, sync_log_id)

                results.append({
                    "account_id": account_id,
                    "display_name": account["display_name"],
                    "status": "error",
                    "error": error_msg,
                    "inserted_count": 0
                })

        sync_duration = (datetime.utcnow() - sync_start).total_seconds()

        logger.info(f"Sync completed for user {user.id}: {total_inserted} transactions in {sync_duration:.1f}s")

        return {
            "status": "completed",
            "total_inserted": total_inserted,
            "accounts_processed": len(accounts),
            "duration_seconds": sync_duration,
            "results": results,
            "synced_at": sync_start.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync failed for user {user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Transaction sync failed: {str(e)}"
        )


@router.get("/accounts", response_model=List[AAAccountOut])
async def list_aa_accounts(
    user: AuthenticatedUser = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db)
) -> List[AAAccountOut]:
    """
    List all linked AA accounts for the authenticated user

    Returns account information including sync status and metadata.
    Accounts are ordered by creation date (most recent first).

    Returns:
        List[AAAccountOut]: List of linked AA accounts
    """
    try:
        accounts = await db.fetch("""
            SELECT id, aa_account_id, display_name, last_sync_at, created_at
            FROM aa_accounts 
            WHERE user_id = $1
            ORDER BY created_at DESC
        """, user.id)

        result = []
        for account in accounts:
            result.append(AAAccountOut(
                account_id=account["id"],
                aa_account_id=account["aa_account_id"],
                display_name=account["display_name"],
                last_sync_at=account["last_sync_at"],
                created_at=account["created_at"]
            ))

        logger.info(f"Listed {len(result)} AA accounts for user {user.id}")
        return result

    except Exception as e:
        logger.error(f"Failed to list AA accounts for user {user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve AA accounts"
        )


@router.get("/sync-logs", response_model=List[AASyncLogOut])
async def list_sync_logs(
    user: AuthenticatedUser = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db),
    limit: int = Query(default=50, le=100, description="Maximum number of logs to return"),
    offset: int = Query(default=0, ge=0, description="Number of logs to skip")
) -> List[AASyncLogOut]:
    """
    List sync logs for the authenticated user

    Returns recent sync activities including status, counts, and error details.
    Useful for monitoring sync health and debugging issues.

    Args:
        limit: Maximum number of logs to return (max 100)
        offset: Number of logs to skip for pagination

    Returns:
        List[AASyncLogOut]: List of sync log entries
    """
    try:
        logs = await db.fetch("""
            SELECT id, account_id, start_ts, end_ts, status, 
                   inserted_count, error_text
            FROM aa_sync_logs 
            WHERE user_id = $1
            ORDER BY start_ts DESC
            LIMIT $2 OFFSET $3
        """, user.id, limit, offset)

        result = []
        for log in logs:
            result.append(AASyncLogOut(
                sync_id=log["id"],
                account_id=log["account_id"],
                start_ts=log["start_ts"],
                end_ts=log["end_ts"],
                status=AASyncStatus(log["status"]),
                inserted_count=log["inserted_count"],
                error_text=log["error_text"]
            ))

        return result

    except Exception as e:
        logger.error(f"Failed to list sync logs for user {user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve sync logs"
        )


def _verify_webhook_signature(body: bytes, signature: str) -> bool:
    """
    Verify webhook signature for security

    Uses HMAC-SHA256 with the configured webhook secret to verify
    that the webhook payload is authentic and hasn't been tampered with.

    Args:
        body: Raw webhook body bytes
        signature: Signature header value

    Returns:
        bool: True if signature is valid
    """
    if not AA_MOCK_WEBHOOK_SECRET or not signature:
        logger.warning("Webhook signature verification skipped (no secret configured)")
        return True  # Allow webhooks in development

    try:
        # Expected format: "sha256=<hash>"
        if not signature.startswith("sha256="):
            return False

        expected_signature = signature[7:]  # Remove "sha256=" prefix

        # Generate signature
        mac = hmac.new(
            AA_MOCK_WEBHOOK_SECRET.encode('utf-8'),
            body,
            hashlib.sha256
        )
        computed_signature = mac.hexdigest()

        # Secure comparison
        return hmac.compare_digest(expected_signature, computed_signature)

    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        return False