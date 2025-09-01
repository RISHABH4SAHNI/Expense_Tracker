# Audit Service for Account Aggregator Operations

The audit service provides comprehensive logging and visibility for AA sync operations with correlation ID support for tracing across worker/scheduler/webhook processes.

## Features

- ✅ **General audit logging** with `record_event()` function
- ✅ **Sync operation context manager** for automatic start/end AASyncLog entries  
- ✅ **Correlation ID support** for tracing across distributed operations
- ✅ **Multiple log levels** (debug, info, warning, error, critical)
- ✅ **Structured event types** for consistent audit trails
- ✅ **Database integration** with existing AA models
- ✅ **Python logging integration** for immediate visibility

## Core Functions

### `record_event(user_id, event_type, payload, level)`

Records individual audit events with structured data.

```python
from app.services.audit import record_event, AuditEventType, AuditLevel

# Record a webhook received event
await record_event(
    user_id="user-123",
    event_type=AuditEventType.WEBHOOK_RECEIVED,
    payload={
        "webhook_type": "transaction_update",
        "account_id": "acc-456"
    },
    level=AuditLevel.INFO,
    correlation_id="corr-789"
)
```

### `sync_context()` - Context Manager

Wraps sync operations with automatic AASyncLog start/end entries.

```python
from app.services.audit import sync_context

async def my_sync_operation(user_id: str, account_id: str):
    async with sync_context(
        user_id=user_id,
        account_id=account_id,
        operation_type="account_sync",
        correlation_id="optional-correlation-id"
    ) as ctx:

        # Perform sync operations
        transactions = await fetch_transactions()

        for tx in transactions:
            result = await process_transaction(tx)
            if result == "inserted":
                ctx["inserted_count"] += 1
            elif result == "skipped":
                ctx["skipped_count"] += 1
            else:
                ctx["error_count"] += 1

        # Context manager automatically:
        # - Creates AASyncLog entry on start
        # - Records audit events for start/end/error
        # - Updates AASyncLog with results on completion
        # - Handles error cases and logging
```

## Event Types

Predefined event types for consistent audit logging:

- **Sync Operations**: `SYNC_START`, `SYNC_END`, `SYNC_ERROR`
- **Webhook Operations**: `WEBHOOK_RECEIVED`, `WEBHOOK_PROCESSED`, `WEBHOOK_ERROR`
- **Consent Operations**: `CONSENT_CREATED`, `CONSENT_UPDATED`, `CONSENT_EXPIRED`
- **Account Operations**: `ACCOUNT_LINKED`, `ACCOUNT_SYNC`
- **Transaction Operations**: `TRANSACTION_UPSERT`, `TRANSACTION_CATEGORIZE`
- **General Operations**: `USER_ACTION`, `SYSTEM_ERROR`, `EXTERNAL_API`

## Database Schema

The audit service automatically creates the `audit_events` table:

```sql
CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    event_type VARCHAR(100) NOT NULL,
    level VARCHAR(20) NOT NULL DEFAULT 'info',
    correlation_id UUID NOT NULL,
    account_id VARCHAR(255),
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

And uses the existing `aa_sync_logs` table for sync operation tracking.

## Correlation ID Tracing

Correlation IDs enable tracing operations across different components:

```python
# Generate correlation ID for a multi-step operation
correlation_id = str(uuid.uuid4())

# 1. Webhook handler
await record_event(
    user_id=user_id,
    event_type=AuditEventType.WEBHOOK_RECEIVED,
    correlation_id=correlation_id,
    payload={"webhook_data": "..."}
)

# 2. Worker processing
async with sync_context(
    user_id=user_id,
    correlation_id=correlation_id,  # Same correlation ID
    operation_type="webhook_triggered_sync"
) as ctx:
    # Sync operations
    pass

# 3. Transaction processing  
await record_event(
    user_id=user_id,
    event_type=AuditEventType.TRANSACTION_UPSERT,
    correlation_id=correlation_id,  # Same correlation ID
    payload={"transaction_id": "tx-123"}
)
```

## Integration Examples

### Webhook Processing

```python
async def process_aa_webhook(payload: dict):
    correlation_id = str(uuid.uuid4())

    await record_event(
        user_id=payload.get("user_id"),
        event_type=AuditEventType.WEBHOOK_RECEIVED,
        payload={"webhook_type": payload.get("type")},
        correlation_id=correlation_id
    )

    try:
        # Process webhook
        result = await handle_webhook(payload, correlation_id)

        await record_event(
            user_id=payload.get("user_id"),
            event_type=AuditEventType.WEBHOOK_PROCESSED,
            payload={"result": result},
            correlation_id=correlation_id
        )
    except Exception as e:
        await record_event(
            user_id=payload.get("user_id"),
            event_type=AuditEventType.WEBHOOK_ERROR,
            payload={"error": str(e)},
            level=AuditLevel.ERROR,
            correlation_id=correlation_id
        )
        raise
```

### Worker Operations

```python
async def categorize_worker(tx_id: str):
    correlation_id = str(uuid.uuid4())

    await record_event(
        user_id=None,  # System operation
        event_type=AuditEventType.TRANSACTION_CATEGORIZE,
        payload={"transaction_id": tx_id, "worker": "categorize_worker"},
        correlation_id=correlation_id
    )

    # Perform categorization
    # ...
```

## Verification

Run the verification script to check audit logs:

```bash
cd server
python verify_audit.py
