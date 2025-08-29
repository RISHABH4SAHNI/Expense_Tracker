"""
Transaction Service Layer
Handles business logic for transaction processing, AA integration, and sync operations
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncpg

from app.services.aa_client import aa_client, ConsentResponse
from app.models.pydantic_models import TransactionIn, SyncResponse

logger = logging.getLogger(__name__)

class TransactionService:
    """
    Service class for handling transaction-related business logic
    """

    def __init__(self):
        self.aa_client = aa_client

    async def initiate_account_linking(self, user_id: str) -> ConsentResponse:
        """
        Initiate account linking flow with Account Aggregator

        Args:
            user_id: User identifier

        Returns:
            ConsentResponse: Consent details including account IDs
        """
        logger.info(f"🔗 Initiating account linking for user: {user_id}")

        try:
            consent = await self.aa_client.simulate_consent_flow(user_id)
            logger.info(f"✅ Account linking successful for user {user_id}: {len(consent.account_ids)} accounts linked")
            return consent

        except Exception as e:
            logger.error(f"❌ Account linking failed for user {user_id}: {e}")
            raise

    async def sync_account_transactions(
        self,
        account_id: str,
        from_date: datetime,
        to_date: Optional[datetime] = None,
        db: Optional[asyncpg.Connection] = None
    ) -> SyncResponse:
        """
        Sync transactions for a specific account from AA

        Args:
            account_id: Account identifier
            from_date: Start date for transaction sync
            to_date: End date for transaction sync (default: now)
            db: Database connection

        Returns:
            SyncResponse: Sync operation results
        """
        logger.info(f"🔄 Starting transaction sync for account: {account_id}")

        if to_date is None:
            to_date = datetime.utcnow()

        try:
            # Fetch transactions from AA
            transactions = await self.aa_client.fetch_transactions_for_account(
                account_id=account_id,
                since=from_date,
                until=to_date
            )

            if not transactions:
                logger.info(f"📭 No transactions found for account {account_id}")
                return SyncResponse(
                    status="success",
                    inserted_count=0,
                    updated_count=0,
                    skipped_count=0,
                    error_count=0,
                    account_id=account_id,
                    from_date=from_date.strftime("%Y-%m-%d"),
                    to_date=to_date.strftime("%Y-%m-%d")
                )

            # Process transactions (insert/update in database)
            sync_result = await self._process_transactions_batch(
                transactions=transactions,
                db=db
            )

            sync_result.account_id = account_id
            sync_result.from_date = from_date.strftime("%Y-%m-%d")
            sync_result.to_date = to_date.strftime("%Y-%m-%d")

            logger.info(f"✅ Transaction sync completed for {account_id}: {sync_result.inserted_count} inserted, {sync_result.updated_count} updated")
            return sync_result

        except Exception as e:
            logger.error(f"❌ Transaction sync failed for account {account_id}: {e}")
            return SyncResponse(
                status="failed",
                inserted_count=0,
                updated_count=0,
                skipped_count=0,
                error_count=1,
                account_id=account_id,
                from_date=from_date.strftime("%Y-%m-%d"),
                to_date=to_date.strftime("%Y-%m-%d")
            )

    async def _process_transactions_batch(
        self,
        transactions: List[TransactionIn],
        db: Optional[asyncpg.Connection] = None
    ) -> SyncResponse:
        """
        Process a batch of transactions (insert/update in database)

        Args:
            transactions: List of transactions to process
            db: Database connection

        Returns:
            SyncResponse: Processing results
        """
        if not db:
            # Mock processing for development mode
            return SyncResponse(
                status="success",
                inserted_count=len([t for t in transactions if t.type.value == "debit"]),
                updated_count=len([t for t in transactions if t.type.value == "credit"]),
                skipped_count=0,
                error_count=0,
                account_id="mock_account",
                from_date="mock_date",
                to_date="mock_date"
            )

        inserted_count = 0
        updated_count = 0
        error_count = 0

        # This is a simplified version - in production you'd want proper batch processing
        for transaction in transactions:
            try:
                # Check if transaction exists
                existing = await db.fetchrow(
                    "SELECT id FROM transactions WHERE bank_transaction_id = $1",
                    transaction.id
                )

                if existing:
                    # Update existing
                    await db.execute("""
                        UPDATE transactions 
                        SET amount = $2, raw_desc = $3, updated_at = $4
                        WHERE bank_transaction_id = $1
                    """, transaction.id, transaction.amount, transaction.raw_desc, datetime.utcnow())
                    updated_count += 1
                else:
                    # Insert new
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

            except Exception as e:
                error_count += 1
                logger.error(f"❌ Failed to process transaction {transaction.id}: {e}")

        return SyncResponse(
            status="success" if error_count == 0 else "partial",
            inserted_count=inserted_count,
            updated_count=updated_count,
            skipped_count=0,
            error_count=error_count,
            account_id="batch_process",
            from_date="batch_date",
            to_date="batch_date"
        )

# Global service instance
transaction_service = TransactionService()