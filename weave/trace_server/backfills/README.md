# ClickHouse Backfill Framework

A minimal, robust framework for managing large-scale ClickHouse data backfills with automatic checkpointing, progress tracking, and error recovery.

## Directory Structure

```
backfills/
├── __init__.py                         # Exports
├── clickhouse_backfill_manager.py      # Core framework (~664 lines)
├── migrations/                          # Backfill definitions
│   ├── 001_calls_complete.backfill.meta
│   └── 001_calls_complete.backfill.sql
└── README.md                            # This file
```

## Philosophy

**Backfills are data operations, not schema migrations.**

- **Backfills** (here): Large-scale data transformations, historical data backfilling, data cleanup
- **Schema Migrations** (`../migrations/`): Table creation/modification, index changes, schema evolution

## Quick Start

### CLI Usage (Recommended for Testing)

```bash
# List all backfills
python -m weave.trace_server.backfills list

# Run a backfill
python -m weave.trace_server.backfills run --database=weave --version=1

# Check status
python -m weave.trace_server.backfills status --database=weave --version=1

# Run with limited batches for testing
python -m weave.trace_server.backfills run --database=weave --version=1 --max-batches=10
```

### Python API

```python
from weave.trace_server.backfills import ClickHouseBackfillManager

manager = ClickHouseBackfillManager(ch_client)

# List backfills
backfills = manager.list_backfills(database="weave")

# Run a backfill
manager.run_backfill(database="weave", version=1)

# Check status
status = manager.get_status(database="weave", version=1)
print(f"Progress: {status['rows_processed']:,} rows")
```

---

## How It Works

### 1. Backfill Definition

Each backfill consists of two files in `migrations/`:

#### **`.backfill.meta`** - Configuration

```json
{
  "migration_version": 1,
  "description": "What this backfill does",
  "batch_size": 1000000,
  "checkpoint_columns": ["project_id", "id"],
  "target_table": "table_name",
  "timeout_seconds": 3600,
  "run_on_startup": false,
  "max_retries": 3
}
```

**Fields:**
- `migration_version`: Unique identifier for this backfill
- `description`: Human-readable description
- `batch_size`: Initial rows per batch (framework reduces on OOM)
- `checkpoint_columns`: Columns used for progress tracking
- `target_table`: Table being populated (for checkpoint queries)
- `timeout_seconds`: Per-batch timeout
- `run_on_startup`: Whether to run automatically when registered
- `max_retries`: Retries per batch before giving up

#### **`.backfill.sql`** - SQL Template

```sql
-- Framework provides: {db}, {batch_size}, {checkpoint_<column>}
INSERT INTO {db}.target_table
SELECT * FROM {db}.source_table
WHERE column > '{checkpoint_column}'
ORDER BY column
LIMIT {batch_size};
```

**Placeholders:**
- `{db}` - Target database name
- `{batch_size}` - Current batch size (may be reduced from initial)
- `{checkpoint_<col>}` - Current checkpoint value for each checkpoint column
- Custom fields from checkpoint JSON (e.g., `{cutover_timestamp}`)

### 2. Framework Features

#### Checkpointing
- Progress saved after every successful batch
- Stored as JSON in `db_management.backfills` table
- Resume from exact position after interruption

#### Batch Processing
- Configurable initial batch size
- Automatic reduction on OOM errors (halves each time)
- Retries with exponential backoff

#### Progress Tracking
```json
{
  "project_id": "abc123",
  "id": "xyz789",
  "current_batch_size": 500000,
  "rows_processed": 5000000,
  "batches_completed": 10,
  "custom_field": "custom_value"
}
```

#### Status Management
- States: `pending`, `running`, `paused`, `completed`, `failed`
- Error logging for troubleshooting
- Timestamps for started/updated/completed

### 3. Integration with Migrations

Backfills are automatically discovered and registered when schema migrations run:

```python
# When you run migrations...
migrator = ClickHouseTraceServerMigrator(ch_client)
migrator.apply_migrations(target_db="weave")

# Backfills in migrations/ are automatically registered
# Check what was registered:
manager = ClickHouseBackfillManager(ch_client)
pending = manager.list_backfills(database="weave", status="pending")
```

---

## Usage Examples

### Basic Operations

```python
from weave.trace_server.backfills import ClickHouseBackfillManager
from clickhouse_connect import get_client

ch_client = get_client(host="localhost", port=8123)
manager = ClickHouseBackfillManager(ch_client)

# List all backfills
backfills = manager.list_backfills(database="weave")
for bf in backfills:
    print(f"v{bf['migration_version']}: {bf['status']} - {bf['rows_processed']:,} rows")

# Run a backfill
manager.run_backfill(database="weave", version=1)

# Check status
status = manager.get_status(database="weave", version=1)
print(f"Status: {status['status']}")
print(f"Progress: {status['rows_processed']:,} rows")
print(f"Checkpoint: {status['checkpoint']}")

# Pause and resume
manager.pause_backfill(database="weave", version=1)
manager.resume_backfill(database="weave", version=1)
```

### Testing with Limited Batches

```python
# Run only 10 batches for testing
manager.run_backfill(database="weave", version=1, max_batches=10)
```

### Monitoring Progress

```python
import time

# Start backfill in background...
# In another process, monitor progress:
while True:
    status = manager.get_status(database="weave", version=1)
    
    if status['status'] == 'completed':
        print("Backfill completed!")
        break
    elif status['status'] == 'failed':
        print(f"Failed: {status['error_log']}")
        break
    else:
        checkpoint = status['checkpoint']
        print(f"Progress: {status['rows_processed']:,} rows, "
              f"Batch {checkpoint.get('batches_completed', 0)}, "
              f"Size: {checkpoint.get('current_batch_size', 'N/A')}")
    
    time.sleep(60)
```

### Error Handling

```python
from weave.trace_server.backfills import BackfillError

try:
    manager.run_backfill(database="weave", version=1)
except BackfillError as e:
    print(f"Backfill error: {e}")
    
    status = manager.get_status(database="weave", version=1)
    print(f"Error log: {status['error_log']}")
    print(f"Last checkpoint: {status['checkpoint']}")
    
    # Resume from checkpoint
    manager.resume_backfill(database="weave", version=1)
except KeyboardInterrupt:
    print("Interrupted - checkpoint saved")
```

---

## Creating a New Backfill

### Step 1: Create Metadata File

`migrations/002_my_backfill.backfill.meta`:
```json
{
  "migration_version": 2,
  "description": "Backfill my_table from source",
  "batch_size": 500000,
  "checkpoint_columns": ["id"],
  "target_table": "my_table",
  "timeout_seconds": 1800,
  "run_on_startup": false,
  "max_retries": 3
}
```

### Step 2: Create SQL Template

`migrations/002_my_backfill.backfill.sql`:
```sql
-- Simple backfill example
INSERT INTO {db}.my_table
SELECT * FROM {db}.source_table
WHERE id > '{checkpoint_id}'
ORDER BY id
LIMIT {batch_size};
```

### Step 3: Deploy and Execute

```python
# Backfill is auto-discovered and registered
manager = ClickHouseBackfillManager(ch_client)
manager.run_backfill(database="weave", version=2)
```

---

## Implementation Details

### Core Components

**ClickHouseBackfillManager** - Main class methods:
- `run_backfill()` - Execute backfill with automatic checkpointing
- `get_status()` - Get detailed status and progress
- `list_backfills()` - List all backfills with optional filters
- `pause_backfill()` / `resume_backfill()` - Pause and resume operations
- `register_pending_backfills()` - Auto-register from migration system

### Database Infrastructure

**Migration 021** creates `db_management.backfills`:
```sql
CREATE TABLE db_management.backfills (
    backfill_id String,              -- "{db_name}_{version}"
    migration_version UInt64,
    db_name String,
    status String,                    -- 'pending', 'running', 'completed', 'failed', 'paused'
    checkpoint_data String,           -- JSON blob with progress and custom fields
    rows_processed UInt64,
    started_at Nullable(DateTime64(3)),
    updated_at DateTime64(3),
    completed_at Nullable(DateTime64(3)),
    error_log Nullable(String)
) ENGINE = MergeTree()
ORDER BY (db_name, migration_version);
```

### Example: calls_complete Backfill

**Goal**: Backfill completed calls from `calls_merged` (AggregatingMergeTree) to `calls_complete` (MergeTree).

**Complexity handled in SQL** (not framework):
1. AggregatingMergeTree finalization with `-Merge` functions
2. Index-friendly batching (LIMIT before GROUP BY)
3. Cutover timestamp calculation (avoids dual-writes)
4. Deduplication near cutover boundary
5. Partial group handling

**Framework handles**:
1. Batch execution loop
2. Checkpoint save/load
3. OOM recovery
4. Progress tracking
5. Status management

---

## Design Principles

1. **Separation of Concerns**: Backfills (data ops) separate from migrations (schema changes)
2. **Simplicity First**: Framework is minimal (~664 lines), complexity lives in SQL
3. **Checkpoint Everything**: Progress saved after every batch
4. **SQL Owns Logic**: Migration-specific complexity stays in SQL templates
5. **Fail Safely**: Automatic checkpointing ensures no data loss on interruption
6. **Observable**: Clear status, progress tracking, and error messages

## What We Intentionally Didn't Build

- ❌ CLI (use Python API directly)
- ❌ Separate error/checkpoint snapshot tables (use JSON blob)
- ❌ Complex error classification (simple retry is enough)
- ❌ Binary search for bad rows (just fail and fix)
- ❌ Progress estimation with ETA (nice-to-have, not essential)
- ❌ Priority queue (process sequentially)
- ❌ Adaptive batch sizing (halve on OOM is sufficient)

---

## Testing Strategy

1. **Unit tests**: Checkpoint save/load, SQL rendering, metadata validation
2. **Integration tests**: Full lifecycle with local ClickHouse
3. **Production testing**: Run with `max_batches=10` first

## Deployment

1. Deploy migration 021 (infrastructure table)
2. Deploy backfill files to `backfills/migrations/` directory
3. Run schema migrations - backfills auto-register
4. Execute: `manager.run_backfill(database="weave", version=1)`
5. Monitor: `manager.get_status(database="weave", version=1)`

---

## Success Criteria

✅ Framework < 700 lines of code (achieved: 664)  
✅ Handles interruption and resumes without data loss  
✅ Processes millions of rows without timeout  
✅ Automatic OOM recovery  
✅ Clear separation between data ops and schema changes  
✅ Reusable for future backfills  
✅ No CLI dependency - simple Python API