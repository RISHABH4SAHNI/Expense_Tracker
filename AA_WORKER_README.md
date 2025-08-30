# AA Worker & Scheduler

Background processing system for Account Aggregator sync operations with retry logic, dead letter queues, and automatic scheduling.

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Scheduler     │───▶│   Redis Queue    │───▶│   AA Worker     │
│   (Periodic)    │    │   "aa_sync"      │    │   (Consumer)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │  Retry Queue     │    │  Sync Account   │
                       │  "aa_sync_retry" │    │  (via sync.py)  │
                       └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │      DLQ         │    │   AASyncLog     │
                       │    "aa_dlq"      │    │   (Database)    │
                       └──────────────────┘    └─────────────────┘
```

## 🔧 Components

### 1. AA Worker (`app/workers/aa_worker.py`)

Background worker that processes AA sync jobs with robust retry logic.

**Features:**
- Listens to `aa_sync` Redis queue
- Processes jobs with payload: `{user_id, account_id, since_ts}`
- Calls `sync.sync_account()` for actual syncing
- Exponential backoff retry (30s, 2m, 5m)
- Dead letter queue for failed jobs
- Comprehensive logging to AASyncLog

**Job Payload:**
```json
{
  "user_id": "uuid",
  "account_id": "aa_account_uuid", 
  "since_ts": "2024-01-15T10:30:00+05:30",
  "retry_count": 0,
  "original_enqueue_time": "2024-01-15T14:00:00+05:30"
}
```

### 2. AA Scheduler (`app/scheduler/aa_scheduler.py`)

Automatic scheduler that enqueues sync jobs for stale accounts.

**Features:**
- Runs every 4 hours (configurable)
- Finds accounts with `last_sync_at` older than threshold
- Only syncs accounts with active consent status
- APScheduler integration with fallback to simple loop
- Environment flag to disable in development

### 3. Helper Functions

**`enqueue_aa_sync(user_id, account_id, since_ts)`**
- Enqueues a sync job to Redis queue
- Used by scheduler and manual triggers
- Returns boolean success status

## 📋 Queue Structure

### Main Queue: `aa_sync`
- Primary job queue for sync operations
- Worker processes jobs from this queue
- Jobs are removed after processing

### Retry Queue: `aa_sync_retry`
- Holds jobs scheduled for retry
- Includes `retry_at` timestamp
- Worker periodically moves ready jobs back to main queue

### Dead Letter Queue: `aa_dlq`
- Jobs that failed after max retries
- Includes failure reason and timestamp
- Requires manual intervention

### Monitoring Queues:
- `aa_sync_completed`: Successful job logs
- `aa_sync_failed`: Failed job logs (before retries)
- `aa_scheduler_events`: Scheduler execution logs

## 🚀 Usage

### Running the Worker

**CLI (Development):**
```bash
# Start the worker
python run_aa_worker.py

# Set environment variables
export REDIS_URL="redis://localhost:6379/0"
export DATABASE_URL="postgresql://user:pass@localhost:5432/db"
export AA_WORKER_MAX_RETRIES=3
```

**Docker (Production):**
```bash
# Add to docker-compose.yml
aa_worker:
  build: ./server
  command: python run_aa_worker.py
  environment:
    - REDIS_URL=redis://redis:6379/0
    - DATABASE_URL=postgresql://expenseuser:expensepass@postgres:5432/expensedb
  depends_on:
    - redis
    - postgres
```

### Running the Scheduler

**CLI (Development):**
```bash
# Start the scheduler
python run_aa_scheduler.py

# Environment variables
export AA_SCHEDULER_ENABLED=true
export AA_SYNC_INTERVAL_HOURS=4
export AA_STALE_THRESHOLD_HOURS=4
```

**Disable in Development:**
```bash
export AA_SCHEDULER_ENABLED=false
```

### Manual Job Enqueuing

**API Endpoint:**
```bash
POST /api/admin/aa/enqueue-sync?user_id=123&account_id=456&since_days=7
```

**Python Code:**
```python
from app.workers.aa_worker import enqueue_aa_sync
from datetime import datetime, timedelta

# Enqueue sync job
since_ts = datetime.utcnow() - timedelta(days=7)
success = await enqueue_aa_sync(
    user_id="user_123",
    account_id="account_uuid", 
    since_ts=since_ts
)
```

## 📊 Monitoring & Admin

### API Endpoints

**Worker Statistics:**
```bash
GET /api/admin/aa/worker/stats
```

**Scheduler Statistics:**
```bash
GET /api/admin/aa/scheduler/stats
```

**Queue Status:**
```bash
GET /api/admin/aa/queue/status
```

**Manual Scheduler Trigger:**
```bash
POST /api/admin/aa/scheduler/trigger
```

**Clear Queues (Development):**
```bash
DELETE /api/admin/aa/queue/clear
```

### Logs & Metrics

**AASyncLog Table:**
- Every sync operation creates a log entry
- Tracks start/end times, counts, errors
- Links to specific accounts and users

**Redis Monitoring:**
```bash
# Check queue sizes
redis-cli llen aa_sync
redis-cli llen aa_sync_retry
redis-cli llen aa_dlq

# View recent completed jobs
redis-cli lrange aa_sync_completed 0 9
```

## 🧪 Testing

**Test Worker Setup:**
```bash
# Test enqueuing and processing
python test_aa_worker.py

# Start worker to process test jobs
python run_aa_worker.py
