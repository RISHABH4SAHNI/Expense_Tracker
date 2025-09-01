"""
Verification script for audit logging functionality

Run this script to verify that audit events and sync logs are being created properly.
"""

import asyncio
import asyncpg
from datetime import datetime, timedelta
from typing import List, Dict


async def verify_audit_logs():
    """Verify audit logs are working by checking recent entries."""

    # Connect to database
    DATABASE_URL = "postgresql://expenseuser:expensepass@localhost:5433/expensedb"

    try:
        conn = await asyncpg.connect(DATABASE_URL)

        print("🔍 Verifying Audit System...")
        print("=" * 50)

        # Check if audit_events table exists and has data
        audit_count = await conn.fetchval("""
            SELECT COUNT(*) FROM audit_events 
            WHERE created_at >= $1
        """, datetime.utcnow() - timedelta(hours=24))

        print(f"✅ Recent audit events (last 24h): {audit_count}")

        # Show recent audit events
        if audit_count > 0:
            recent_events = await conn.fetch("""
                SELECT event_type, level, correlation_id, account_id, created_at
                FROM audit_events 
                WHERE created_at >= $1
                ORDER BY created_at DESC
                LIMIT 10
            """, datetime.utcnow() - timedelta(hours=24))

            print("\n📋 Recent Audit Events:")
            for event in recent_events:
                print(f"  • {event['event_type']} ({event['level']}) - {event['created_at']}")
                print(f"    Correlation ID: {event['correlation_id']}")
                if event['account_id']:
                    print(f"    Account ID: {event['account_id']}")
                print()

        # Check AASyncLog entries
        sync_count = await conn.fetchval("""
            SELECT COUNT(*) FROM aa_sync_logs 
            WHERE created_at >= $1
        """, datetime.utcnow() - timedelta(hours=24))

        print(f"✅ Recent sync log entries (last 24h): {sync_count}")

        # Show recent sync logs
        if sync_count > 0:
            recent_syncs = await conn.fetch("""
                SELECT status, inserted_count, start_ts, end_ts, error_text
                FROM aa_sync_logs 
                WHERE created_at >= $1
                ORDER BY created_at DESC
                LIMIT 5
            """, datetime.utcnow() - timedelta(hours=24))

            print("\n📊 Recent Sync Operations:")
            for sync in recent_syncs:
                duration = ""
                if sync['end_ts'] and sync['start_ts']:
                    duration_seconds = (sync['end_ts'] - sync['start_ts']).total_seconds()
                    duration = f" ({duration_seconds:.2f}s)"

                print(f"  • Status: {sync['status']}{duration}")
                print(f"    Inserted: {sync['inserted_count']} transactions")
                if sync['error_text']:
                    print(f"    Error: {sync['error_text'][:100]}...")
                print()

        await conn.close()
        print("✅ Audit verification completed successfully!")

    except Exception as e:
        print(f"❌ Error verifying audit logs: {e}")


if __name__ == "__main__":
    asyncio.run(verify_audit_logs())