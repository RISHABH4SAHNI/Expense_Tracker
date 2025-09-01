"""
Audit Service for Account Aggregator Operations

Small audit logger for AA operations providing:
- record_event(user_id, event_type, payload, level) for general audit logging
- sync_context manager that wraps sync operations with start/end AASyncLog rows
- correlation_id support for tracing across worker/scheduler/webhook operations

Ensures clear audit trail for each sync/webhook operation.
"""

import uuid
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Union, AsyncContextManager
from contextlib import asynccontextmanager
from enum import Enum

import asyncpg

from app.database import get_db, db_pool
from app.models.aa_models import AASyncStatus

logger = logging.getLogger(__name__)


class AuditLevel(str, Enum):
    """Audit log levels for different types of events"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEventType(str, Enum):
    """Standard audit event types for AA operations"""
    # Sync operations
    SYNC_START = "sync_start"
    SYNC_END = "sync_end"
    SYNC_ERROR = "sync_error"

    # Webhook operations
    WEBHOOK_RECEIVED = "webhook_received"
    WEBHOOK_PROCESSED = "webhook_processed" 
    WEBHOOK_ERROR = "webhook_error"

    # Consent operations
    CONSENT_CREATED = "consent_created"
    CONSENT_UPDATED = "consent_updated"
    CONSENT_EXPIRED = "consent_expired"

    # Account operations
    ACCOUNT_LINKED = "account_linked"
    ACCOUNT_SYNC = "account_sync"

    # Transaction operations
    TRANSACTION_UPSERT = "transaction_upsert"
    TRANSACTION_CATEGORIZE = "transaction_categorize"

    # General operations
    USER_ACTION = "user_action"
    SYSTEM_ERROR = "system_error"
    EXTERNAL_API = "external_api"


async def record_event(
    user_id: Optional[str],
    event_type: Union[str, AuditEventType],
    payload: Optional[Dict[str, Any]] = None,
    level: Union[str, AuditLevel] = AuditLevel.INFO,
    correlation_id: Optional[str] = None,
    account_id: Optional[str] = None,
    db: Optional[asyncpg.Connection] = None
) -> Optional[str]:
    """
    Record an audit event for AA operations.

    Args:
        user_id: User identifier (can be None for system events)
        event_type: Type of event being logged
        payload: Event-specific data to be stored as JSON
        level: Log level (debug, info, warning, error, critical)
        correlation_id: Optional correlation ID for tracing operations
        account_id: Optional AA account ID for account-specific events
        db: Optional database connection

    Returns:
        str: Audit event ID if successfully recorded, None otherwise
    """
    try:
        # Convert enums to strings
        if isinstance(event_type, AuditEventType):
            event_type = event_type.value
        if isinstance(level, AuditLevel):
            level = level.value

        # Generate correlation ID if not provided
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Prepare payload for JSON storage
        payload_json = None
        if payload:
            try:
                # Ensure payload is JSON serializable
                payload_json = json.dumps(payload, default=str)
            except (TypeError, ValueError) as e:
                logger.warning(f"Failed to serialize audit payload: {e}")
                payload_json = json.dumps({"error": "Failed to serialize payload", "original_error": str(e)})

        # Get database connection
        if db is None:
            if not db_pool:
                logger.warning("No database connection available for audit logging")
                return None
            async with db_pool.acquire() as conn:
                return await _insert_audit_event(
                    conn, user_id, event_type, payload_json, level, correlation_id, account_id
                )
        else:
            return await _insert_audit_event(
                db, user_id, event_type, payload_json, level, correlation_id, account_id
            )

    except Exception as e:
        logger.error(f"Failed to record audit event {event_type}: {e}")
        return None


async def _insert_audit_event(
    conn: asyncpg.Connection,
    user_id: Optional[str],
    event_type: str,
    payload_json: Optional[str],
    level: str,
    correlation_id: str,
    account_id: Optional[str]
) -> str:
    """Internal function to insert audit event into database."""

    # Create audit events table if it doesn't exist
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID,
            event_type VARCHAR(100) NOT NULL,
            level VARCHAR(20) NOT NULL DEFAULT 'info',
            correlation_id UUID NOT NULL,
            account_id VARCHAR(255),
            payload JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for efficient queries
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_events_user_id ON audit_events(user_id)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_events_event_type ON audit_events(event_type)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_events_correlation_id ON audit_events(correlation_id)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events(created_at DESC)
    """)

    # Insert audit event
    audit_id = await conn.fetchval("""
        INSERT INTO audit_events (
            user_id, event_type, level, correlation_id, account_id, payload
        ) VALUES ($1, $2, $3, $4, $5, $6::jsonb)
        RETURNING id
    """, user_id, event_type, level, correlation_id, account_id, payload_json)

    # Also log to Python logger for immediate visibility
    log_level = getattr(logging, level.upper(), logging.INFO)
    extra_info = {
        "correlation_id": correlation_id,
        "user_id": user_id,
        "account_id": account_id,
        "audit_id": str(audit_id)
    }

    logger.log(log_level, f"AUDIT {event_type}: {payload_json or 'No payload'}", extra=extra_info)

    return str(audit_id)


@asynccontextmanager
async def sync_context(
    user_id: str,
    account_id: Optional[str] = None,
    operation_type: str = "account_sync",
    correlation_id: Optional[str] = None,
    db: Optional[asyncpg.Connection] = None
) -> AsyncContextManager[Dict[str, Any]]:
    """
    Context manager for AA sync operations that automatically creates start/end AASyncLog entries.

    Usage:
        async with sync_context(user_id, account_id, "account_sync") as ctx:
            # Perform sync operations
            ctx["inserted_count"] = 10
            ctx["custom_data"] = {"key": "value"}

    Args:
        user_id: User identifier
        account_id: Optional AA account ID
        operation_type: Type of sync operation
        correlation_id: Optional correlation ID for tracing
        db: Optional database connection

    Yields:
        Dict[str, Any]: Context dictionary for storing operation results
    """
    # Generate correlation ID if not provided
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    start_time = datetime.utcnow()
    sync_log_id = None
    context = {
        "correlation_id": correlation_id,
        "inserted_count": 0,
        "skipped_count": 0,
        "error_count": 0,
        "operation_type": operation_type,
        "metadata": {}
    }

    try:
        # Get database connection
        if db is None:
            if not db_pool:
                logger.warning("No database connection available for sync context")
                yield context
                return
            async with db_pool.acquire() as conn:
                async with _sync_context_impl(conn, user_id, account_id, operation_type, 
                                            correlation_id, start_time, context) as ctx:
                    yield ctx
        else:
            async with _sync_context_impl(db, user_id, account_id, operation_type,
                                        correlation_id, start_time, context) as ctx:
                yield ctx

    except Exception as e:
        logger.error(f"Sync context error for user {user_id}: {e}")
        # Ensure we still record the failure
        await record_event(
            user_id=user_id,
            event_type=AuditEventType.SYNC_ERROR,
            payload={
                "operation_type": operation_type,
                "error": str(e),
                "account_id": account_id
            },
            level=AuditLevel.ERROR,
            correlation_id=correlation_id,
            account_id=account_id,
            db=db
        )
        raise


@asynccontextmanager
async def _sync_context_impl(
    conn: asyncpg.Connection,
    user_id: str,
    account_id: Optional[str],
    operation_type: str,
    correlation_id: str,
    start_time: datetime,
    context: Dict[str, Any]
):
    """Internal implementation of sync context manager."""

    sync_log_id = None

    try:
        # Create AASyncLog entry for start
        sync_log_id = await conn.fetchval("""
            INSERT INTO aa_sync_logs (
                user_id, account_id, start_ts, status, created_at
            ) VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """, user_id, account_id, start_time, AASyncStatus.RUNNING.value, start_time)

        context["sync_log_id"] = str(sync_log_id)

        # Record audit event for sync start
        await record_event(
            user_id=user_id,
            event_type=AuditEventType.SYNC_START,
            payload={
                "operation_type": operation_type,
                "sync_log_id": str(sync_log_id),
                "account_id": account_id
            },
            level=AuditLevel.INFO,
            correlation_id=correlation_id,
            account_id=account_id,
            db=conn
        )

        logger.info(f"Started sync operation {operation_type} for user {user_id}", 
                   extra={"correlation_id": correlation_id, "sync_log_id": str(sync_log_id)})

        # Yield context for operation execution
        yield context

        # Update AASyncLog entry for successful completion
        end_time = datetime.utcnow()
        await conn.execute("""
            UPDATE aa_sync_logs 
            SET end_ts = $1, status = $2, inserted_count = $3, updated_at = $4
            WHERE id = $5
        """, end_time, AASyncStatus.COMPLETED.value, context.get("inserted_count", 0), 
             end_time, sync_log_id)

        # Record audit event for sync completion
        await record_event(
            user_id=user_id,
            event_type=AuditEventType.SYNC_END,
            payload={
                "operation_type": operation_type,
                "sync_log_id": str(sync_log_id),
                "inserted_count": context.get("inserted_count", 0),
                "skipped_count": context.get("skipped_count", 0),
                "error_count": context.get("error_count", 0),
                "duration_seconds": (end_time - start_time).total_seconds(),
                "account_id": account_id,
                "metadata": context.get("metadata", {})
            },
            level=AuditLevel.INFO,
            correlation_id=correlation_id,
            account_id=account_id,
            db=conn
        )

        logger.info(f"Completed sync operation {operation_type} for user {user_id}", 
                   extra={"correlation_id": correlation_id, "sync_log_id": str(sync_log_id), 
                          "inserted_count": context.get("inserted_count", 0)})

    except Exception as e:
        # Update AASyncLog entry for failure if we have sync_log_id
        if sync_log_id:
            end_time = datetime.utcnow()
            await conn.execute("""
                UPDATE aa_sync_logs 
                SET end_ts = $1, status = $2, error_text = $3, updated_at = $4
                WHERE id = $5
            """, end_time, AASyncStatus.FAILED.value, str(e), end_time, sync_log_id)

        # Record audit event for sync failure
        await record_event(
            user_id=user_id,
            event_type=AuditEventType.SYNC_ERROR,
            payload={
                "operation_type": operation_type,
                "sync_log_id": str(sync_log_id) if sync_log_id else None,
                "error": str(e),
                "account_id": account_id,
                "context": context
            },
            level=AuditLevel.ERROR,
            correlation_id=correlation_id,
            account_id=account_id,
            db=conn
        )

        logger.error(f"Failed sync operation {operation_type} for user {user_id}: {e}", 
                    extra={"correlation_id": correlation_id, "sync_log_id": str(sync_log_id) if sync_log_id else None})

        raise
"""
Audit Service for Account Aggregator Operations

Small audit logger for AA operations providing:
- record_event(user_id, event_type, payload, level) for general audit logging
- sync_context manager that wraps sync operations with start/end AASyncLog rows
- correlation_id support for tracing across worker/scheduler/webhook operations

Ensures clear audit trail for each sync/webhook operation.
"""

import uuid
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Union, AsyncContextManager
from contextlib import asynccontextmanager
from enum import Enum

import asyncpg

from app.database import db_pool
from app.models.aa_models import AASyncStatus

logger = logging.getLogger(__name__)


class AuditLevel(str, Enum):
    """Audit log levels for different types of events"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEventType(str, Enum):
    """Standard audit event types for AA operations"""
    # Sync operations
    SYNC_START = "sync_start"
    SYNC_END = "sync_end"
    SYNC_ERROR = "sync_error"

    # Webhook operations
    WEBHOOK_RECEIVED = "webhook_received"
    WEBHOOK_PROCESSED = "webhook_processed" 
    WEBHOOK_ERROR = "webhook_error"

    # Consent operations
    CONSENT_CREATED = "consent_created"
    CONSENT_UPDATED = "consent_updated"
    CONSENT_EXPIRED = "consent_expired"

    # Account operations
    ACCOUNT_LINKED = "account_linked"
    ACCOUNT_SYNC = "account_sync"

    # Transaction operations
    TRANSACTION_UPSERT = "transaction_upsert"
    TRANSACTION_CATEGORIZE = "transaction_categorize"

    # General operations
    USER_ACTION = "user_action"
    SYSTEM_ERROR = "system_error"
    EXTERNAL_API = "external_api"


async def record_event(
    user_id: Optional[str],
    event_type: Union[str, AuditEventType],
    payload: Optional[Dict[str, Any]] = None,
    level: Union[str, AuditLevel] = AuditLevel.INFO,
    correlation_id: Optional[str] = None,
    account_id: Optional[str] = None,
    db: Optional[asyncpg.Connection] = None
) -> Optional[str]:
    """
    Record an audit event for AA operations.

    Args:
        user_id: User identifier (can be None for system events)
        event_type: Type of event being logged
        payload: Event-specific data to be stored as JSON
        level: Log level (debug, info, warning, error, critical)
        correlation_id: Optional correlation ID for tracing operations
        account_id: Optional AA account ID for account-specific events
        db: Optional database connection

    Returns:
        str: Audit event ID if successfully recorded, None otherwise
    """
    try:
        # Convert enums to strings
        if isinstance(event_type, AuditEventType):
            event_type = event_type.value
        if isinstance(level, AuditLevel):
            level = level.value

        # Generate correlation ID if not provided
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Prepare payload for JSON storage
        payload_json = None
        if payload:
            try:
                # Ensure payload is JSON serializable
                payload_json = json.dumps(payload, default=str)
            except (TypeError, ValueError) as e:
                logger.warning(f"Failed to serialize audit payload: {e}")
                payload_json = json.dumps({"error": "Failed to serialize payload", "original_error": str(e)})

        # Get database connection
        if db is None:
            if not db_pool:
                logger.warning("No database connection available for audit logging")
                return None
            async with db_pool.acquire() as conn:
                return await _insert_audit_event(
                    conn, user_id, event_type, payload_json, level, correlation_id, account_id
                )
        else:
            return await _insert_audit_event(
                db, user_id, event_type, payload_json, level, correlation_id, account_id
            )

    except Exception as e:
        logger.error(f"Failed to record audit event {event_type}: {e}")
        return None


async def _insert_audit_event(
    conn: asyncpg.Connection,
    user_id: Optional[str],
    event_type: str,
    payload_json: Optional[str],
    level: str,
    correlation_id: str,
    account_id: Optional[str]
) -> str:
    """Internal function to insert audit event into database."""

    # Create audit events table if it doesn't exist
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID,
            event_type VARCHAR(100) NOT NULL,
            level VARCHAR(20) NOT NULL DEFAULT 'info',
            correlation_id UUID NOT NULL,
            account_id VARCHAR(255),
            payload JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for efficient queries
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_events_user_id ON audit_events(user_id)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_events_event_type ON audit_events(event_type)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_events_correlation_id ON audit_events(correlation_id)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events(created_at DESC)
    """)

    # Insert audit event
    audit_id = await conn.fetchval("""
        INSERT INTO audit_events (
            user_id, event_type, level, correlation_id, account_id, payload
        ) VALUES ($1, $2, $3, $4, $5, $6::jsonb)
        RETURNING id
    """, user_id, event_type, level, correlation_id, account_id, payload_json)

    # Also log to Python logger for immediate visibility
    log_level = getattr(logging, level.upper(), logging.INFO)
    extra_info = {
        "correlation_id": correlation_id,
        "user_id": user_id,
        "account_id": account_id,
        "audit_id": str(audit_id)
    }

    logger.log(log_level, f"AUDIT {event_type}: {payload_json or 'No payload'}", extra=extra_info)

    return str(audit_id)


@asynccontextmanager
async def sync_context(
    user_id: str,
    account_id: Optional[str] = None,
    operation_type: str = "account_sync",
    correlation_id: Optional[str] = None,
    db: Optional[asyncpg.Connection] = None
) -> AsyncContextManager[Dict[str, Any]]:
    """
    Context manager for AA sync operations that automatically creates start/end AASyncLog entries.

    Usage:
        async with sync_context(user_id, account_id, "account_sync") as ctx:
            # Perform sync operations
            ctx["inserted_count"] = 10
            ctx["custom_data"] = {"key": "value"}

    Args:
        user_id: User identifier
        account_id: Optional AA account ID
        operation_type: Type of sync operation
        correlation_id: Optional correlation ID for tracing
        db: Optional database connection

    Yields:
        Dict[str, Any]: Context dictionary for storing operation results
    """
    # Generate correlation ID if not provided
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    start_time = datetime.utcnow()
    context = {
        "correlation_id": correlation_id,
        "inserted_count": 0,
        "skipped_count": 0,
        "error_count": 0,
        "operation_type": operation_type,
        "metadata": {}
    }

    try:
        # Get database connection
        if db is None:
            if not db_pool:
                logger.warning("No database connection available for sync context")
                yield context
                return
            async with db_pool.acquire() as conn:
                async with _sync_context_impl(conn, user_id, account_id, operation_type, 
                                            correlation_id, start_time, context) as ctx:
                    yield ctx
        else:
            async with _sync_context_impl(db, user_id, account_id, operation_type,
                                        correlation_id, start_time, context) as ctx:
                yield ctx

    except Exception as e:
        logger.error(f"Sync context error for user {user_id}: {e}")
        # Ensure we still record the failure
        await record_event(
            user_id=user_id,
            event_type=AuditEventType.SYNC_ERROR,
            payload={
                "operation_type": operation_type,
                "error": str(e),
                "account_id": account_id
            },
            level=AuditLevel.ERROR,
            correlation_id=correlation_id,
            account_id=account_id,
            db=db
        )
        raise


@asynccontextmanager
async def _sync_context_impl(
    conn: asyncpg.Connection,
    user_id: str,
    account_id: Optional[str],
    operation_type: str,
    correlation_id: str,
    start_time: datetime,
    context: Dict[str, Any]
):
    """Internal implementation of sync context manager."""

    sync_log_id = None

    try:
        # Create AASyncLog entry for start
        sync_log_id = await conn.fetchval("""
            INSERT INTO aa_sync_logs (
                user_id, account_id, start_ts, status, created_at
            ) VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """, user_id, account_id, start_time, AASyncStatus.RUNNING.value, start_time)

        context["sync_log_id"] = str(sync_log_id)

        # Record audit event for sync start
        await record_event(
            user_id=user_id,
            event_type=AuditEventType.SYNC_START,
            payload={
                "operation_type": operation_type,
                "sync_log_id": str(sync_log_id),
                "account_id": account_id
            },
            level=AuditLevel.INFO,
            correlation_id=correlation_id,
            account_id=account_id,
            db=conn
        )

        logger.info(f"Started sync operation {operation_type} for user {user_id}", 
                   extra={"correlation_id": correlation_id, "sync_log_id": str(sync_log_id)})

        # Yield context for operation execution
        yield context

        # Update AASyncLog entry for successful completion
        end_time = datetime.utcnow()
        await conn.execute("""
            UPDATE aa_sync_logs 
            SET end_ts = $1, status = $2, inserted_count = $3, updated_at = $4
            WHERE id = $5
        """, end_time, AASyncStatus.COMPLETED.value, context.get("inserted_count", 0), 
             end_time, sync_log_id)

        # Record audit event for sync completion
        await record_event(
            user_id=user_id,
            event_type=AuditEventType.SYNC_END,
            payload={
                "operation_type": operation_type,
                "sync_log_id": str(sync_log_id),
                "inserted_count": context.get("inserted_count", 0),
                "skipped_count": context.get("skipped_count", 0),
                "error_count": context.get("error_count", 0),
                "duration_seconds": (end_time - start_time).total_seconds(),
                "account_id": account_id,
                "metadata": context.get("metadata", {})
            },
            level=AuditLevel.INFO,
            correlation_id=correlation_id,
            account_id=account_id,
            db=conn
        )

        logger.info(f"Completed sync operation {operation_type} for user {user_id}", 
                   extra={"correlation_id": correlation_id, "sync_log_id": str(sync_log_id), 
                          "inserted_count": context.get("inserted_count", 0)})

    except Exception as e:
        # Update AASyncLog entry for failure if we have sync_log_id
        if sync_log_id:
            end_time = datetime.utcnow()
            await conn.execute("""
                UPDATE aa_sync_logs 
                SET end_ts = $1, status = $2, error_text = $3, updated_at = $4
                WHERE id = $5
            """, end_time, AASyncStatus.FAILED.value, str(e), end_time, sync_log_id)

        # Record audit event for sync failure
        await record_event(
            user_id=user_id,
            event_type=AuditEventType.SYNC_ERROR,
            payload={
                "operation_type": operation_type,
                "sync_log_id": str(sync_log_id) if sync_log_id else None,
                "error": str(e),
                "account_id": account_id,
                "context": context
            },
            level=AuditLevel.ERROR,
            correlation_id=correlation_id,
            account_id=account_id,
            db=conn
        )

        logger.error(f"Failed sync operation {operation_type} for user {user_id}: {e}", 
                    extra={"correlation_id": correlation_id, "sync_log_id": str(sync_log_id) if sync_log_id else None})

        raise