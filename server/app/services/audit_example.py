"""
Usage example for audit service integration

Shows how to integrate the audit service with existing sync operations
and webhook processing for complete traceability.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import asyncpg

from app.services.audit import record_event, sync_context, AuditEventType, AuditLevel
from app.services.aa_client import aa_client


logger = logging.getLogger(__name__)


async def sync_account_with_audit(
    user_id: str,
    account_id: str,
    aa_account_id: str,
    since_ts: Optional[datetime] = None,
    correlation_id: Optional[str] = None,
    db: Optional[asyncpg.Connection] = None
) -> Dict[str, Any]:
    """
    Example of account sync with comprehensive audit logging.

    This shows how to integrate the audit service with existing sync operations
    for complete traceability across the sync lifecycle.
    """

    # Use the sync_context manager to handle AASyncLog entries automatically
    async with sync_context(
        user_id=user_id,
        account_id=account_id,
        operation_type="account_sync_with_audit",
        correlation_id=correlation_id,
        db=db
    ) as ctx:

        try:
            # Record external API call start
            await record_event(
                user_id=user_id,
                event_type=AuditEventType.EXTERNAL_API,
                payload={
                    "api": "aa_client.fetch_transactions",
                    "account_id": aa_account_id,
                    "since_ts": str(since_ts) if since_ts else None
                },
                level=AuditLevel.INFO,
                correlation_id=ctx["correlation_id"],
                account_id=account_id,
                db=db
            )

            # Fetch transactions from AA client (simulated)
            transactions = await aa_client.fetch_transactions(
                account_id=aa_account_id,
                since_ts=since_ts,
                limit=1000
            )

            # Process transactions
            for tx in transactions:
                try:
                    # Simulate transaction processing
                    # In real code, this would call upsert_transaction
                    result = "inserted"  # or "skipped"

                    if result == "inserted":
                        ctx["inserted_count"] += 1
                        # Record individual transaction audit
                        await record_event(
                            user_id=user_id,
                            event_type=AuditEventType.TRANSACTION_UPSERT,
                            payload={
                                "transaction_id": tx.get("id"),
                                "amount": str(tx.get("amount", 0)),
                                "result": result
                            },
                            level=AuditLevel.DEBUG,
                            correlation_id=ctx["correlation_id"],
                            account_id=account_id,
                            db=db
                        )
                    else:
                        ctx["skipped_count"] += 1

                except Exception as tx_error:
                    ctx["error_count"] += 1
                    logger.error(f"Failed to process transaction {tx.get('id')}: {tx_error}")

            # Store metadata in context for audit trail
            ctx["metadata"] = {
                "aa_account_id": aa_account_id,
                "transaction_count": len(transactions),
                "api_response_size": len(str(transactions))
            }

            return {
                "status": "completed",
                "correlation_id": ctx["correlation_id"],
                "sync_log_id": ctx["sync_log_id"],
                "inserted_count": ctx["inserted_count"],
                "skipped_count": ctx["skipped_count"],
                "error_count": ctx["error_count"]
            }

        except Exception as e:
            # Error handling is automatic via context manager
            # Additional custom error logging can be added here
            logger.error(f"Sync failed for account {aa_account_id}: {e}")
            raise


async def process_webhook_with_audit(
    webhook_payload: Dict[str, Any],
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Example of webhook processing with audit logging.
    """

    # Record webhook received
    await record_event(
        user_id=webhook_payload.get("user_id"),
        event_type=AuditEventType.WEBHOOK_RECEIVED,
        payload={
            "webhook_type": webhook_payload.get("type"),
            "account_id": webhook_payload.get("account_id"),
            "payload_size": len(str(webhook_payload))
        },
        level=AuditLevel.INFO,
        correlation_id=correlation_id,
        account_id=webhook_payload.get("account_id")
    )

    try:
        # Process webhook (simulated)
        await asyncio.sleep(0.1)  # Simulate processing

        # Record successful processing
        await record_event(
            user_id=webhook_payload.get("user_id"),
            event_type=AuditEventType.WEBHOOK_PROCESSED,
            payload={
                "webhook_type": webhook_payload.get("type"),
                "processing_result": "success"
            },
            level=AuditLevel.INFO,
            correlation_id=correlation_id,
            account_id=webhook_payload.get("account_id")
        )

        return {"status": "processed", "correlation_id": correlation_id}

    except Exception as e:
        # Record webhook error
        await record_event(
            user_id=webhook_payload.get("user_id"),
            event_type=AuditEventType.WEBHOOK_ERROR,
            payload={
                "webhook_type": webhook_payload.get("type"),
                "error": str(e)
            },
            level=AuditLevel.ERROR,
            correlation_id=correlation_id,
            account_id=webhook_payload.get("account_id")
        )
        raise