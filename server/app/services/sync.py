"""
Idempotent Ingestion & Deduplication Service

Provides sync helpers for safe, repeatable transaction ingestion:
- normalize_tx_id: Creates deterministic hash for deduplication
- upsert_transaction: Inserts or skips based on hash, returns status
- sync_account: Fetches from AA and upserts transactions, returns summary
- enqueue_categorize: Pushes categorization jobs to Redis queue

Designed for idempotent operation - can run repeatedly without duplicating data.
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal

import asyncpg
import redis.asyncio as redis

from app.database import get_db
from app.services.aa_client import aa_client
from app.models.aa_models import AASyncStatus
from app.models.pydantic_models import TransactionIn, TransactionType

logger = logging.getLogger(__name__)

# Redis client (will be set from main.py like other modules)
redis_client = None

def set_redis_client(client):
    """Set Redis client from main.py"""
    global redis_client
    redis_client = client


def normalize_tx_id(raw_tx: Dict[str, Any]) -> str:
    """
    Create deterministic hash from transaction data for deduplication.

    Uses: user_id + account_id + bank_tx_id + amount + timestamp
    This ensures the same transaction data always produces the same hash.

    Args:
        raw_tx: Raw transaction dictionary containing:
            - id: Bank transaction ID
            - account_id: Account identifier
            - amount: Transaction amount
            - ts: Transaction timestamp
            - user_id: User identifier (if available, else account_id used)

    Returns:
        str: SHA-256 hash (first 32 characters for readability)
    """
    try:
        # Extract key fields for hash generation
        user_id = raw_tx.get('user_id', raw_tx.get('account_id', ''))
        account_id = raw_tx.get('account_id', '')
        tx_id = raw_tx.get('id', '')
        amount = str(raw_tx.get('amount', ''))
        timestamp = raw_tx.get('ts', '')

        # Create deterministic string
        hash_components = [
            str(user_id),
            str(account_id), 
            str(tx_id),
            str(amount),
            str(timestamp)
        ]

        hash_string = '|'.join(hash_components)

        # Generate SHA-256 hash
        hash_obj = hashlib.sha256(hash_string.encode('utf-8'))
        tx_hash = hash_obj.hexdigest()[:32]  # First 32 chars for readability

        logger.debug(f"Generated tx_hash {tx_hash} for tx_id {tx_id}")
        return tx_hash

    except Exception as e:
        logger.error(f"Failed to normalize transaction ID: {e}")
        # Fallback to bank transaction ID if hash generation fails
        return raw_tx.get('id', f'fallback_{uuid.uuid4().hex[:16]}')


async def upsert_transaction(
    user_id: str, 
    tx_dict: Dict[str, Any], 
    db: Optional[asyncpg.Connection] = None
) -> str:
    """
    Insert transaction if not exists, skip if duplicate based on tx_hash.

    Args:
        user_id: User identifier
        tx_dict: Transaction dictionary from AA client
        db: Database connection (optional)

    Returns:
        str: "inserted" if new transaction added, "skipped" if duplicate
    """
    # Ensure user_id is included in transaction data for hash generation
    tx_dict_with_user = {**tx_dict, 'user_id': user_id}

    # Generate deterministic hash for deduplication
    tx_hash = normalize_tx_id(tx_dict_with_user)

    try:
        # Use provided connection or get a new one
        if db is None:
            from app.database import db_pool
            if not db_pool:
                logger.warning("No database connection available")
                return "skipped"

            async with db_pool.acquire() as conn:
                return await _perform_upsert(conn, user_id, tx_dict, tx_hash)
        else:
            return await _perform_upsert(db, user_id, tx_dict, tx_hash)

    except Exception as e:
        logger.error(f"Failed to upsert transaction {tx_dict.get('id', 'unknown')}: {e}")
        return "skipped"


async def _perform_upsert(
    conn: asyncpg.Connection,
    user_id: str,
    tx_dict: Dict[str, Any], 
    tx_hash: str
) -> str:
    """Internal function to perform the actual upsert operation."""

    # Check if transaction already exists by tx_hash (our dedup key)
    existing = await conn.fetchrow(
        "SELECT id FROM transactions WHERE bank_transaction_id = $1",
        tx_hash  # Use our normalized hash as the bank_transaction_id
    )

    if existing:
        logger.debug(f"Transaction {tx_dict.get('id')} already exists (hash: {tx_hash})")
        return "skipped"

    # Parse transaction data
    try:
        # Parse timestamp
        ts_str = tx_dict.get('ts', '')
        if ts_str.endswith('Z'):
            ts_str = ts_str[:-1] + '+00:00'
        tx_timestamp = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))

        # Parse amount
        amount = Decimal(str(tx_dict.get('amount', 0)))

        # Parse type
        tx_type = tx_dict.get('type', 'debit').lower()
        if tx_type not in ['debit', 'credit']:
            tx_type = 'debit'

    except Exception as e:
        logger.error(f"Failed to parse transaction data: {e}")
        return "skipped"

    # Insert new transaction
    try:
        await conn.execute("""
            INSERT INTO transactions (
                bank_transaction_id, user_id, ts, amount, type, 
                raw_desc, account_id, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, 
        tx_hash,  # Use our normalized hash as bank_transaction_id
        user_id,
        tx_timestamp,
        amount,
        tx_type,
        tx_dict.get('raw_desc', ''),
        tx_dict.get('account_id', ''),
        datetime.utcnow(),
        datetime.utcnow()
        )

        logger.debug(f"Inserted transaction {tx_dict.get('id')} with hash {tx_hash}")
        return "inserted"

    except Exception as e:
        logger.error(f"Failed to insert transaction: {e}")
        return "skipped"


async def sync_account(
    account_row: Dict[str, Any],
    since_ts: Optional[datetime] = None,
    db: Optional[asyncpg.Connection] = None
) -> Dict[str, Any]:
    """
    Sync transactions for an account from AA client.

    Fetches transactions, upserts each one, counts results, and logs to AASyncLog.

    Args:
        account_row: Dictionary with account info (must have 'aa_account_id', 'user_id', 'id')
        since_ts: Fetch transactions since this timestamp (optional)
        db: Database connection (optional)

    Returns:
        Dict: Sync summary with inserted_count, skipped_count, error_count, etc.
    """
    aa_account_id = account_row.get('aa_account_id')
    user_id = account_row.get('user_id')
    account_id = account_row.get('id')

    if not all([aa_account_id, user_id]):
        return {
            "status": "failed",
            "error": "Missing required account fields",
            "inserted_count": 0,
            "skipped_count": 0,
            "error_count": 1
        }

    # Start sync logging
    start_time = datetime.utcnow()
    sync_log_id = None

    try:
        # Use provided connection or get a new one
        if db is None:
            from app.database import db_pool
            if not db_pool:
                logger.warning("No database connection available")
                return {"status": "failed", "error": "No database", "inserted_count": 0, "skipped_count": 0, "error_count": 1}

            async with db_pool.acquire() as conn:
                return await _perform_sync(conn, account_row, since_ts, start_time)
        else:
            return await _perform_sync(db, account_row, since_ts, start_time)

    except Exception as e:
        logger.error(f"Sync failed for account {aa_account_id}: {e}")
        return {
            "status": "failed", 
            "error": str(e),
            "inserted_count": 0,
            "skipped_count": 0, 
            "error_count": 1
        }


async def _perform_sync(
    conn: asyncpg.Connection,
    account_row: Dict[str, Any],
    since_ts: Optional[datetime],
    start_time: datetime
) -> Dict[str, Any]:
    """Internal function to perform the actual sync operation."""

    aa_account_id = account_row['aa_account_id']
    user_id = account_row['user_id']
    account_id = account_row.get('id')

    # Create sync log entry
    sync_log_id = await conn.fetchval("""
        INSERT INTO aa_sync_logs (user_id, account_id, start_ts, status)
        VALUES ($1, $2, $3, $4) RETURNING id
    """, user_id, account_id, start_time, AASyncStatus.RUNNING.value)

    try:
        # Fetch transactions from AA client
        logger.info(f"Fetching transactions for account {aa_account_id} since {since_ts}")
        transactions = await aa_client.fetch_transactions(
            account_id=aa_account_id,
            since_ts=since_ts,
            limit=1000  # Reasonable batch size
        )

        logger.info(f"Fetched {len(transactions)} transactions for account {aa_account_id}")

        # Process each transaction
        inserted_count = 0
        skipped_count = 0
        error_count = 0

        for tx in transactions:
            try:
                result = await upsert_transaction(user_id, tx, conn)
                if result == "inserted":
                    inserted_count += 1
                    # Enqueue for categorization
                    tx_id = await _get_transaction_id_by_hash(conn, normalize_tx_id({**tx, 'user_id': user_id}))
                    if tx_id:
                        await enqueue_categorize(tx_id)
                elif result == "skipped":
                    skipped_count += 1
                else:
                    error_count += 1

            except Exception as e:
                logger.error(f"Failed to process transaction {tx.get('id', 'unknown')}: {e}")
                error_count += 1

        # Update sync log as completed
        end_time = datetime.utcnow()
        await conn.execute("""
            UPDATE aa_sync_logs 
            SET end_ts = $1, status = $2, inserted_count = $3, updated_at = $4
            WHERE id = $5
        """, end_time, AASyncStatus.COMPLETED.value, inserted_count, end_time, sync_log_id)

        # Update account last_sync_at
        if account_id:
            await conn.execute("""
                UPDATE aa_accounts 
                SET last_sync_at = $1, updated_at = $2
                WHERE id = $3
            """, end_time, end_time, account_id)

        logger.info(f"Sync completed for account {aa_account_id}: {inserted_count} inserted, {skipped_count} skipped, {error_count} errors")

        return {
            "status": "completed",
            "inserted_count": inserted_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
            "sync_duration_seconds": (end_time - start_time).total_seconds(),
            "sync_log_id": str(sync_log_id)
        }

    except Exception as e:
        # Update sync log as failed
        end_time = datetime.utcnow()
        await conn.execute("""
            UPDATE aa_sync_logs 
            SET end_ts = $1, status = $2, error_text = $3, updated_at = $4
            WHERE id = $5
        """, end_time, AASyncStatus.FAILED.value, str(e), end_time, sync_log_id)

        logger.error(f"Sync failed for account {aa_account_id}: {e}")
        raise


async def _get_transaction_id_by_hash(conn: asyncpg.Connection, tx_hash: str) -> Optional[str]:
    """Get transaction UUID by normalized hash."""
    try:
        result = await conn.fetchval(
            "SELECT id FROM transactions WHERE bank_transaction_id = $1",
            tx_hash
        )
        return str(result) if result else None
    except Exception as e:
        logger.error(f"Failed to get transaction ID by hash: {e}")
        return None


async def enqueue_categorize(tx_id: str) -> bool:
    """
    Enqueue transaction categorization job to Redis queue.

    Args:
        tx_id: Transaction UUID to categorize

    Returns:
        bool: True if successfully enqueued, False otherwise
    """
    if not redis_client:
        logger.warning("Redis not available, skipping categorization job")
        return False

    try:
        job_data = {
            "tx_id": tx_id,
            "created_at": datetime.utcnow().isoformat(),
            "job_type": "categorize_transaction"
        }

        # Push to Redis list (same pattern as existing code)
        await redis_client.lpush("categorization_jobs", json.dumps(job_data))

        logger.debug(f"Enqueued categorization job for transaction {tx_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to enqueue categorization job for {tx_id}: {e}")
        return False


# Convenience function for bulk sync operations
async def sync_all_user_accounts(
    user_id: str,
    since_ts: Optional[datetime] = None,
    db: Optional[asyncpg.Connection] = None
) -> List[Dict[str, Any]]:
    """
    Sync all AA accounts for a user.

    Args:
        user_id: User identifier
        since_ts: Fetch transactions since this timestamp (optional)
        db: Database connection (optional)

    Returns:
        List[Dict]: List of sync results for each account
    """
    try:
        # Use provided connection or get a new one
        if db is None:
            from app.database import db_pool
            if not db_pool:
                logger.warning("No database connection available")
                return []

            async with db_pool.acquire() as conn:
                return await _sync_all_accounts(conn, user_id, since_ts)
        else:
            return await _sync_all_accounts(db, user_id, since_ts)

    except Exception as e:
        logger.error(f"Failed to sync accounts for user {user_id}: {e}")
        return []


async def _sync_all_accounts(
    conn: asyncpg.Connection, 
    user_id: str, 
    since_ts: Optional[datetime]
) -> List[Dict[str, Any]]:
    """Internal function to sync all accounts for a user."""

    # Get all AA accounts for user
    accounts = await conn.fetch("""
        SELECT id, user_id, aa_account_id, display_name
        FROM aa_accounts 
        WHERE user_id = $1
        ORDER BY created_at
    """, user_id)

    if not accounts:
        logger.info(f"No AA accounts found for user {user_id}")
        return []

    results = []
    for account in accounts:
        account_dict = dict(account)
        logger.info(f"Syncing account {account_dict['aa_account_id']} for user {user_id}")

        try:
            result = await sync_account(account_dict, since_ts, conn)
            result['account_id'] = account_dict['aa_account_id']
            result['display_name'] = account_dict.get('display_name', '')
            results.append(result)

        except Exception as e:
            logger.error(f"Failed to sync account {account_dict['aa_account_id']}: {e}")
            results.append({
                "status": "failed",
                "error": str(e),
                "account_id": account_dict['aa_account_id'],
                "display_name": account_dict.get('display_name', ''),
                "inserted_count": 0,
                "skipped_count": 0,
                "error_count": 1
            })

    logger.info(f"Completed sync for {len(results)} accounts for user {user_id}")
    return results
