"""
Transaction routes for Expense Tracker API
Handles transaction sync, webhook processing, and CRUD operations
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
import asyncpg
import redis.asyncio as redis
import json
import logging
from typing import List, Optional
from datetime import datetime
import uuid

from app.services.transaction_service import transaction_service
from app.database import get_db
from app.models.pydantic_models import (
    TransactionIn, TransactionDB, SyncResponse, TransactionList,
    TransactionType, TransactionCategory
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Redis client for job queuing (will be set from main.py)
redis_client = None

def set_redis_client(client):
    """Set Redis client from main.py"""
    global redis_client
    redis_client = client

async def enqueue_categorize(tx_id: str) -> bool:
    """
    Enqueue transaction categorization job using RQ
    Args:
        tx_id: Transaction ID to categorize
    Returns:
        bool: True if successfully enqueued, False otherwise
    """
    # Use RQ helper function
    from app.utils.enqueue_categorize import enqueue_categorize as rq_enqueue
    return rq_enqueue(tx_id)

@router.post("/link-account")
async def link_account(user_id: str):
    """
    Initiate account linking with Account Aggregator

    This endpoint simulates the AA consent flow where users grant permission
    to access their bank account data.
    """
    logger.info(f"🔗 Account linking request for user: {user_id}")

    try:
        consent = await transaction_service.initiate_account_linking(user_id)

        return {
            "status": "success",
            "message": "Account linking initiated successfully",
            "consent_handle": consent.consent_handle,
            "account_ids": consent.account_ids,
            "redirect_url": consent.redirect_url,
            "expires_at": consent.expires_at.isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Account linking failed: {e}")
        raise HTTPException(status_code=500, detail=f"Account linking failed: {str(e)}")

@router.post("/sync", response_model=SyncResponse)
async def sync_transactions(
    transactions: List[TransactionIn],
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Bulk sync transactions from bank accounts
    Accepts a list of TransactionIn objects and inserts them into database
    """
    logger.info(f"🔄 Starting bulk sync for {len(transactions)} transactions")

    # Input validation
    if not transactions:
        raise HTTPException(status_code=400, detail="No transactions provided")

    if len(transactions) > 1000:  # Reasonable limit
        raise HTTPException(status_code=400, detail="Too many transactions in single request (max: 1000)")

    if not db:
        # Mock response for development mode
        logger.info("📋 Development mode: returning mock sync response")
        return SyncResponse(
            status="success",
            inserted_count=len(transactions),
            updated_count=0,
            skipped_count=0,
            error_count=0,
            account_id=transactions[0].account_id if transactions else "mock_account",
            from_date="2024-01-01",
            to_date="2024-01-31"
        )

    # Statistics counters
    inserted_count = 0
    updated_count = 0
    skipped_count = 0
    error_count = 0
    errors = []

    try:
        # Process transactions in batches for better performance
        for transaction in transactions:
            try:
                # Check if transaction already exists
                existing = await db.fetchrow(
                    "SELECT id FROM transactions WHERE bank_transaction_id = $1",
                    transaction.id
                )

                if existing:
                    # Update existing transaction
                    await db.execute("""
                        UPDATE transactions 
                        SET amount = $2, raw_desc = $3, updated_at = $4
                        WHERE bank_transaction_id = $1
                    """, transaction.id, transaction.amount, transaction.raw_desc, datetime.utcnow())
                    updated_count += 1
                    logger.debug(f"📝 Updated transaction: {transaction.id}")
                else:
                    # Insert new transaction
                    await db.execute("""
                        INSERT INTO transactions (
                            bank_transaction_id, ts, amount, type, raw_desc, account_id,
                            created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, 
                    transaction.id, transaction.ts, transaction.amount, 
                    transaction.type.value, transaction.raw_desc, transaction.account_id,
                    datetime.utcnow(), datetime.utcnow())

                    inserted_count += 1
                    logger.debug(f"➕ Inserted transaction: {transaction.id}")

                    # Enqueue categorization job for new transactions
                    await enqueue_categorize(transaction.id)

            except Exception as e:
                error_count += 1
                error_msg = f"Failed to process transaction {transaction.id}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"❌ {error_msg}")
                continue

        # Log summary
        logger.info(f"""
        📊 Bulk sync completed:
        - Inserted: {inserted_count}
        - Updated: {updated_count}
        - Skipped: {skipped_count}
        - Errors: {error_count}
        """)

        return SyncResponse(
            status="success" if error_count == 0 else "partial" if inserted_count + updated_count > 0 else "failed",
            inserted_count=inserted_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            error_count=error_count,
            account_id=transactions[0].account_id,
            from_date="bulk_sync",
            to_date="bulk_sync"
        )

    except Exception as e:
        logger.error(f"❌ Bulk sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk sync failed: {str(e)}")

@router.post("/sync-from-aa")
async def sync_from_aa(
    account_id: str,
    from_date: str,
    to_date: Optional[str] = None,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Sync transactions directly from Account Aggregator for a specific account

    This endpoint fetches transactions from the AA and stores them in the database.
    """
    logger.info(f"🏦 AA sync request for account: {account_id}")

    try:
        # Parse dates
        from_datetime = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        to_datetime = None
        if to_date:
            to_datetime = datetime.fromisoformat(to_date.replace('Z', '+00:00'))

        # Use transaction service to sync from AA
        sync_result = await transaction_service.sync_account_transactions(
            account_id=account_id,
            from_date=from_datetime,
            to_date=to_datetime,
            db=db
        )

        # Enqueue categorization jobs for new transactions
        if sync_result.inserted_count > 0:
            logger.info(f"🤖 Enqueuing categorization for {sync_result.inserted_count} new transactions")

        return sync_result

    except ValueError as e:
        logger.error(f"❌ Invalid date format: {e}")
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DD)")
    except Exception as e:
        logger.error(f"❌ AA sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"AA sync failed: {str(e)}")

@router.post("/webhook")
async def transaction_webhook(
    transaction: TransactionIn,
    background_tasks: BackgroundTasks,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Webhook endpoint for receiving single transaction from Account Aggregator
    Inserts transaction and enqueues categorization job
    """
    logger.info(f"📨 Webhook received transaction: {transaction.id}")

    # Input validation
    if not transaction.id or not transaction.account_id:
        raise HTTPException(status_code=400, detail="Transaction ID and account ID are required")

    if not db:
        # Mock response for development mode
        logger.info("📋 Development mode: webhook processed successfully")
        await enqueue_categorize(transaction.id)
        return SyncResponse(
            status="success",
            inserted_count=1,
            updated_count=0,
            skipped_count=0,
            error_count=0,
            account_id=transaction.account_id,
            from_date=transaction.ts.strftime("%Y-%m-%d"),
            to_date=transaction.ts.strftime("%Y-%m-%d")
        )

    try:
        # Check if transaction already exists
        existing = await db.fetchrow(
            "SELECT id FROM transactions WHERE bank_transaction_id = $1",
            transaction.id
        )

        if existing:
            logger.info(f"⚠️ Transaction {transaction.id} already exists, skipping")
            return {
                "status": "skipped",
                "message": "Transaction already exists",
                "transaction_id": transaction.id
            }

        # Insert new transaction
        await db.execute("""
            INSERT INTO transactions (
                bank_transaction_id, ts, amount, type, raw_desc, account_id,
                created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, 
        transaction.id, transaction.ts, transaction.amount, 
        transaction.type.value, transaction.raw_desc, transaction.account_id,
        datetime.utcnow(), datetime.utcnow())

        logger.info(f"✅ Webhook transaction inserted: {transaction.id}")

        # Enqueue categorization job in background
        background_tasks.add_task(enqueue_categorize, transaction.id)

        return {
            "status": "success",
            "message": "Transaction processed and categorization job enqueued",
            "transaction_id": transaction.id
        }

    except Exception as e:
        logger.error(f"❌ Webhook processing failed for {transaction.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process webhook: {str(e)}")

@router.get("/", response_model=TransactionList)
async def get_transactions(
    db: asyncpg.Connection = Depends(get_db),
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    category: Optional[TransactionCategory] = Query(None, description="Filter by category"),
    transaction_type: Optional[TransactionType] = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=200, description="Number of transactions to return"),
    offset: int = Query(0, ge=0, description="Number of transactions to skip")
):
    """Get transactions with filtering and pagination"""
    logger.info(f"📋 Fetching transactions: limit={limit}, offset={offset}")

    if not db:
        # Mock data for development mode
        mock_transactions = [
            TransactionDB(
                id="txn_001",
                ts=datetime(2024, 1, 15, 10, 30, 0),
                amount=250.00,
                type=TransactionType.DEBIT,
                raw_desc="SWIGGY*ORDER",
                account_id="acc_12345",
                merchant="Swiggy",
                category=TransactionCategory.FOOD,
                processed_at=datetime.utcnow(),
                created_at=datetime.utcnow()
            ),
            TransactionDB(
                id="txn_002", 
                ts=datetime(2024, 1, 14, 15, 45, 0),
                amount=1200.00,
                type=TransactionType.DEBIT,
                raw_desc="BIG BAZAAR MUMBAI",
                account_id="acc_12345",
                merchant="Big Bazaar",
                category=TransactionCategory.SHOPPING,
                processed_at=datetime.utcnow(),
                created_at=datetime.utcnow()
            )
        ]

        logger.info(f"📋 Fetched {len(transactions)} transactions")
        return TransactionList(
            transactions=mock_transactions,
            total_count=len(mock_transactions),
            page=1,
            page_size=limit
        )

    try:

        # Build dynamic query based on filters
        query = """
            SELECT bank_transaction_id as id, ts, amount, type, raw_desc, 
                account_id, merchant, category, processed_at, created_at, updated_at
            FROM transactions 
            WHERE 1=1
        """
        params = []
        param_count = 0

        if account_id:
            param_count += 1
            query += f" AND account_id = ${param_count}"
            params.append(account_id)

        if category:
            param_count += 1
            query += f" AND category = ${param_count}"
            params.append(category.value)

        if transaction_type:
            param_count += 1
            query += f" AND type = ${param_count}"
            params.append(transaction_type.value)

        # Add ordering and pagination
        query += " ORDER BY ts DESC"

        param_count += 1
        query += f" LIMIT ${param_count}"
        params.append(limit)

        param_count += 1
        query += f" OFFSET ${param_count}"
        params.append(offset)

        # Execute query
        rows = await db.fetch(query, *params)

        # Get total count for pagination
        count_query = "SELECT COUNT(*) FROM transactions WHERE 1=1"
        count_params = []
        count_param_count = 0

        if account_id:
            count_param_count += 1
            count_query += f" AND account_id = ${count_param_count}"
            count_params.append(account_id)

        if category:
            count_param_count += 1
            count_query += f" AND category = ${count_param_count}"
            count_params.append(category.value)

        if transaction_type:
            count_param_count += 1
            count_query += f" AND type = ${count_param_count}"
            count_params.append(transaction_type.value)

        total_count = await db.fetchval(count_query, *count_params)

        # Convert rows to TransactionDB objects
        transactions = []
        for row in rows:
            transactions.append(TransactionDB(
                id=row['id'],
                ts=row['ts'],
                amount=row['amount'],
                type=TransactionType(row['type']),
                raw_desc=row['raw_desc'],
                account_id=row['account_id'],
                merchant=row['merchant'],
                category=TransactionCategory(row['category']) if row['category'] else None,
                processed_at=row['processed_at'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            ))

        return TransactionList(
            transactions=transactions,
            total_count=total_count,
            page=(offset // limit) + 1,
            page_size=limit
        )

    except Exception as e:
        logger.error(f"❌ Failed to fetch transactions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch transactions: {str(e)}")