# Idempotent Transaction Sync

This module provides safe, repeatable transaction ingestion with automatic deduplication and comprehensive logging.

## ✨ Key Features

- **Idempotent Operations**: Safe to run multiple times without duplicating data
- **Deterministic Hashing**: Consistent transaction identification across runs
- **Automatic Deduplication**: Uses hash-based duplicate detection
- **Comprehensive Logging**: Full audit trail via `AASyncLog` table
- **Background Processing**: Automatic categorization job queuing
- **Error Handling**: Graceful failure handling with detailed error reporting

## 🔧 Core Functions

### `normalize_tx_id(raw_tx) -> str`
Creates a deterministic SHA-256 hash from transaction data:
- **Input**: `user_id + account_id + bank_tx_id + amount + timestamp`
- **Output**: 32-character hash for deduplication
- **Purpose**: Ensures identical transactions always produce the same ID

```python
from app.services.sync import normalize_tx_id

tx = {
    "id": "bank_tx_123",
    "user_id": "user_456", 
    "account_id": "acc_789",
    "amount": 150.50,
    "ts": "2024-01-15T10:30:00+05:30"
}

hash_id = normalize_tx_id(tx)  # Returns: "a1b2c3d4e5f6..."
```

### `upsert_transaction(user_id, tx_dict, db=None) -> str`
Inserts transaction if new, skips if duplicate:
- **Returns**: `"inserted"` or `"skipped"`
- **Deduplication**: Uses normalized hash as `bank_transaction_id`
- **Database**: Creates new connection if not provided

```python
result = await upsert_transaction("user_123", tx_dict)
# Returns: "inserted" | "skipped"
```

### `sync_account(account_row, since_ts=None, db=None) -> dict`
Syncs all transactions for an account:
- **Fetches**: Transactions from AA client
- **Processes**: Each transaction via `upsert_transaction`
- **Logs**: Complete operation to `AASyncLog` table
- **Queues**: Categorization jobs for new transactions

```python
account = {
    "id": "aa_account_uuid",
    "user_id": "user_123", 
    "aa_account_id": "hdfc_user_123_1",
    "display_name": "HDFC ****1234"
}

result = await sync_account(account, since_ts=datetime.now() - timedelta(days=7))
# Returns: {
#     "status": "completed",
#     "inserted_count": 15,
#     "skipped_count": 0,
#     "error_count": 0,
#     "sync_duration_seconds": 2.3,
#     "sync_log_id": "uuid..."
# }
```

### `enqueue_categorize(tx_id) -> bool`
Queues transaction for background categorization:
- **Queue**: Redis list `categorization_jobs`
- **Format**: JSON with `tx_id`, `created_at`, `job_type`
- **Returns**: `True` if successfully queued

## 🌐 API Endpoints

### Sync Single Account
```bash
POST /api/sync/account/{account_id}?user_id=123&since_days=7
```

### Sync All User Accounts  
```bash
POST /api/sync/user/{user_id}?since_days=7
```

### Test Hash Normalization
```bash
GET /api/sync/test/normalize
```

## 🧪 Testing Idempotent Behavior

Run the test script to verify sync operations are truly idempotent:

```bash
# Run idempotent test
python test_sync_idempotent.py

# Expected output:
# ✅ First sync: 15 inserted, 0 skipped  
# ✅ Second sync: 0 inserted, 15 skipped
# 🎉 IDEMPOTENT TEST PASSED!
```

## 📊 Database Schema

The sync process uses several database tables:

- **transactions**: Stores transaction data with `bank_transaction_id` as dedup key
- **aa_sync_logs**: Audit trail for each sync operation
- **aa_accounts**: Account info with `last_sync_at` timestamp
- **categorization_jobs**: Redis queue for background processing

## ⚡ Performance Considerations

- **Batch Size**: Limited to 1000 transactions per sync call
- **Connection Pooling**: Reuses database connections when provided
- **Background Jobs**: Categorization happens asynchronously
- **Indexing**: Optimized queries on `bank_transaction_id` and `user_id`

## 🔒 Error Handling

- **Database Failures**: Graceful degradation, detailed error logging
- **AA Client Errors**: Retry logic and error classification  
- **Redis Unavailable**: Continues without background jobs
- **Parse Errors**: Skips malformed transactions, logs issues

## 📝 Logging & Monitoring

All sync operations create entries in `aa_sync_logs` with:
- Start/end timestamps
- Inserted/skipped/error counts
- Full error messages for failures
- Sync duration metrics

View sync history:
```sql
SELECT * FROM aa_sync_logs 
WHERE user_id = 'user_123' 
ORDER BY start_ts DESC;
