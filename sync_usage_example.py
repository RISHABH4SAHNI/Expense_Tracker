#!/usr/bin/env python3
"""
Usage Example: Idempotent Transaction Sync

Demonstrates how to use the sync helpers for safe transaction ingestion.
"""

import asyncio
import sys
from datetime import datetime, timedelta

# Add server directory to path
sys.path.append('./server')

from app.services.sync import (
    normalize_tx_id,
    upsert_transaction, 
    sync_account,
    sync_all_user_accounts,
    enqueue_categorize
)
from app.database import get_db

async def example_usage():
    """Example showing how to use sync functions."""

    print("📚 Sync Helper Usage Examples")
    print("=" * 40)

    # Example 1: Create deterministic transaction hash
    print("\n1️⃣ Normalize Transaction ID (for deduplication)")
    sample_transaction = {
        "id": "bank_tx_12345",
        "user_id": "user_abc",
        "account_id": "account_xyz", 
        "amount": 299.99,
        "ts": "2024-01-15T14:30:00+05:30"
    }

    tx_hash = normalize_tx_id(sample_transaction)
    print(f"Transaction: {sample_transaction['id']}")
    print(f"Normalized Hash: {tx_hash}")
    print("✅ Same transaction will always produce the same hash")

    # Example 2: Upsert single transaction
    print("\n2️⃣ Upsert Single Transaction")
    print("Usage: result = await upsert_transaction(user_id, tx_dict)")
    print("Returns: 'inserted' or 'skipped'")

    # Example 3: Sync entire account
    print("\n3️⃣ Sync Account Transactions")
    account_row = {
        "id": "aa_account_uuid",
        "user_id": "user_123",
        "aa_account_id": "hdfc_user_123_1",
        "display_name": "HDFC Bank ****1234"
    }

    print("Account to sync:", account_row)
    print("Usage: result = await sync_account(account_row, since_ts)")
    print("Returns: {status, inserted_count, skipped_count, error_count, ...}")

    # Example 4: Sync all user accounts
    print("\n4️⃣ Sync All User Accounts")
    print("Usage: results = await sync_all_user_accounts(user_id, since_ts)")
    print("Returns: List of sync results for each account")

    # Example 5: Enqueue categorization
    print("\n5️⃣ Enqueue Categorization Job")
    print("Usage: success = await enqueue_categorize(transaction_id)")
    print("Returns: True if job queued successfully")

    print("\n🎯 Key Benefits:")
    print("✅ Idempotent - safe to run multiple times")
    print("✅ Automatic deduplication via deterministic hashing")
    print("✅ Comprehensive logging via AASyncLog")
    print("✅ Background categorization jobs")

if __name__ == "__main__":
    asyncio.run(example_usage())