"""
RQ Worker for Transaction Categorization
Processes transactions from Redis queue "categorize"
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any
import asyncpg
from rq import Worker, Queue, Connection
import redis
from datetime import datetime

from app.services.parser import parse_transaction
from app.database import db_pool, set_db_pool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection setup for worker
async def setup_db_connection():
    """Setup database connection for the worker"""
    database_url = os.getenv("DATABASE_URL", "postgresql://expenseuser:expensepass@localhost:5432/expensedb")

    try:
        pool = await asyncpg.create_pool(database_url)
        set_db_pool(pool)
        logger.info("✅ Worker connected to PostgreSQL")
        return pool
    except Exception as e:
        logger.error(f"❌ Worker failed to connect to database: {e}")
        return None

async def load_transaction_by_id(tx_id: str) -> Optional[Dict[str, Any]]:
    """Load transaction from database by ID"""
    if not db_pool:
        logger.error("Database pool not available")
        return None

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, bank_transaction_id, ts, amount, type, raw_desc, 
                       account_id, merchant, category, processed_at
                FROM transactions 
                WHERE bank_transaction_id = $1
            """, tx_id)

            if row:
                return dict(row)
            else:
                logger.warning(f"Transaction not found: {tx_id}")
                return None

    except Exception as e:
        logger.error(f"Error loading transaction {tx_id}: {e}")
        return None

async def save_parsed_transaction(tx_id: str, parsed_data: Dict[str, Any]) -> bool:
    """Save parsed merchant and category back to database"""
    if not db_pool:
        logger.error("Database pool not available")
        return False

    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE transactions 
                SET merchant = $1, category = $2, processed_at = $3, updated_at = $4
                WHERE bank_transaction_id = $5
            """, 
                parsed_data["merchant_candidate"],
                parsed_data["category_candidate"], 
                datetime.utcnow(),
                datetime.utcnow(),
                tx_id
            )
            logger.info(f"✅ Updated transaction {tx_id} with merchant: {parsed_data['merchant_candidate']}, category: {parsed_data['category_candidate']}")
            return True

    except Exception as e:
        logger.error(f"Error saving parsed transaction {tx_id}: {e}")
        return False

async def update_rollups_table(tx_data: Dict[str, Any], parsed_data: Dict[str, Any]) -> bool:
    """Update rollups/summary tables (placeholder for future implementation)"""
    # TODO: Implement rollup logic for:
    # - Monthly category summaries
    # - Merchant spending patterns
    # - Account balance tracking

    logger.info(f"📊 Rollup update placeholder for transaction {tx_data['bank_transaction_id']}")

    # Placeholder: Could update monthly spending by category
    if not db_pool:
        return False

    try:
        # Example rollup logic - this could be expanded
        async with db_pool.acquire() as conn:
            # Simple example: could track monthly spending by category
            await conn.execute("""
                -- Placeholder for rollup table updates
                -- Example: INSERT INTO monthly_category_rollups ...
                SELECT 1
            """)
        return True
    except Exception as e:
        logger.error(f"Error updating rollups: {e}")
        return False

async def check_anomaly_and_notify(tx_data: Dict[str, Any], parsed_data: Dict[str, Any]) -> bool:
    """Check for spending anomalies and send notifications if needed"""
    try:
        amount = float(tx_data['amount'])
        category = parsed_data['category_candidate']

        # Simple anomaly detection rules (can be made more sophisticated)
        anomaly_thresholds = {
            'food': 2000.0,
            'shopping': 5000.0, 
            'transport': 1000.0,
            'entertainment': 1500.0,
            'other': 3000.0
        }

        threshold = anomaly_thresholds.get(category, 3000.0)

        if amount > threshold:
            logger.warning(f"🚨 Anomaly detected: {tx_data['bank_transaction_id']} - Amount {amount} exceeds threshold {threshold} for category {category}")

            # TODO: Implement actual notification logic
            # - Send email/SMS alerts
            # - Push notifications to mobile app
            # - Slack/Discord webhooks

            # Placeholder notification
            notification_message = f"High spending alert: ₹{amount} spent on {parsed_data['merchant_candidate']} ({category})"
            logger.info(f"📱 Notification: {notification_message}")

            return True  # Anomaly detected

        return False  # No anomaly

    except Exception as e:
        logger.error(f"Error in anomaly detection: {e}")
        return False

def categorize_transaction_job(tx_id: str):
    """
    Main RQ job function for categorizing transactions
    This function runs synchronously in the RQ worker process
    """
    logger.info(f"🔄 Processing categorization job for transaction: {tx_id}")

    # Create new event loop for this job (since RQ runs synchronously)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Run the async workflow
        result = loop.run_until_complete(_categorize_transaction_async(tx_id))
        return result
    finally:
        loop.close()

async def _categorize_transaction_async(tx_id: str) -> Dict[str, Any]:
    """Async implementation of transaction categorization workflow"""
    try:
        # Step 1: Setup database connection if needed
        if not db_pool:
            await setup_db_connection()

        # Step 2: Load transaction by ID
        tx_data = await load_transaction_by_id(tx_id)
        if not tx_data:
            return {"success": False, "error": "Transaction not found"}

        # Step 3: Skip if already processed
        if tx_data.get('processed_at'):
            logger.info(f"Transaction {tx_id} already processed, skipping")
            return {"success": True, "status": "already_processed"}

        # Step 4: Parse transaction using parser service
        parsed_data = await parse_transaction(tx_data['raw_desc'])

        # Step 5: Save merchant/category back to database
        save_success = await save_parsed_transaction(tx_id, parsed_data)
        if not save_success:
            return {"success": False, "error": "Failed to save parsed data"}

        # Step 6: Update rollups table
        await update_rollups_table(tx_data, parsed_data)

        # Step 7: Check for anomalies and send notifications
        is_anomaly = await check_anomaly_and_notify(tx_data, parsed_data)

        result = {
            "success": True,
            "transaction_id": tx_id,
            "merchant": parsed_data["merchant_candidate"],
            "category": parsed_data["category_candidate"],
            "confidence": parsed_data["confidence"],
            "anomaly_detected": is_anomaly,
            "processed_at": datetime.utcnow().isoformat()
        }

        logger.info(f"✅ Successfully processed transaction {tx_id}")
        return result

    except Exception as e:
        logger.error(f"❌ Error processing transaction {tx_id}: {e}")
        return {"success": False, "error": str(e)}

def run_worker():
    """Main function to run the RQ worker"""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Connect to Redis
    redis_conn = redis.from_url(redis_url)

    # Create queue
    queue = Queue('categorize', connection=redis_conn)

    logger.info("🚀 Starting RQ worker for 'categorize' queue...")
    logger.info(f"Redis URL: {redis_url}")

    # Start worker
    with Connection(redis_conn):
        worker = Worker([queue])
        worker.work()

if __name__ == '__main__':
    run_worker()