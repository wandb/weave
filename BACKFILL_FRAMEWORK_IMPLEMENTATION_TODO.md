# ClickHouse Backfill Framework Implementation TODO

**Philosophy**: Build a minimal, flexible framework that handles checkpoint persistence and batch execution. Keep migration-specific complexity in the SQL, not the framework.

---

## Overview

### Framework Responsibilities (Keep Simple)
- ✅ Checkpoint persistence (save/load position)
- ✅ Batch execution loop
- ✅ SQL variable substitution
- ✅ Simple retry with batch size reduction on OOM
- ✅ Status tracking
- ✅ Basic CLI (run, status, pause, resume, list)

### Migration-Specific Logic (Lives in SQL)
- The specific backfill SQL handles its own complexity:
  - Cutover timestamps
  - Deduplication windows
  - AggregatingMergeTree GROUP BY logic
  - Index-friendly batching strategies
  - Business logic filters

---

## Phase 1: Core Infrastructure & Schema

### 1.1 Database Schema (Single Table)

#### Create backfill tracking table
- [ ] Create migration file: `migrations/020_backfill_infrastructure.up.sql`
  - [ ] Define `db_management.backfills` table:
    ```sql
    CREATE TABLE db_management.backfills (
        backfill_id String,                      -- Unique ID: "{db_name}_{migration_version}"
        migration_version UInt64,                -- Associated migration version
        db_name String,                          -- Target database name
        status String,                           -- 'pending', 'running', 'completed', 'failed', 'paused'
        checkpoint_data String,                  -- JSON blob: flexible for any checkpoint state
        rows_processed UInt64,                   -- Total rows successfully processed
        started_at Nullable(DateTime64(3)),      -- When backfill started
        updated_at DateTime64(3) DEFAULT now64(3), -- Last update timestamp
        completed_at Nullable(DateTime64(3)),    -- When backfill completed
        error_log Nullable(String)               -- Last error or path to error file
    ) ENGINE = MergeTree()
    ORDER BY (db_name, migration_version);
    ```
  - [ ] Support replicated mode (ENGINE = ReplicatedMergeTree) when configured

- [ ] Create corresponding `020_backfill_infrastructure.down.sql` for rollback

**Note**: No separate error or checkpoint snapshot tables. Errors log to files, checkpoints stored as JSON blob.

---

### 1.2 Backfill File Format

#### Metadata file format (*.backfill.meta)
- [ ] Define JSON schema:
    ```json
    {
      "migration_version": 21,
      "description": "Backfill calls_complete from calls_merged table",
      "batch_size": 1000000,
      "checkpoint_columns": ["project_id", "id"],
      "timeout_seconds": 3600,
      "run_on_startup": false,
      "max_retries": 3
    }
    ```

**Field descriptions**:
- `migration_version`: Links backfill to migration
- `description`: Human-readable description
- `batch_size`: Initial number of rows per batch (framework will halve on OOM)
- `checkpoint_columns`: List of columns used for WHERE clause generation
- `timeout_seconds`: Per-batch timeout
- `run_on_startup`: Whether to run inline during deployment
- `max_retries`: Retries per batch before giving up

**Removed complexity**: No estimated_rows, no checkpoint_strategy, no fallback arrays, no cutover_config, no aggregation_config, no validation queries, no priorities.

---

#### Backfill SQL file format (*.backfill.sql)
- [ ] Define template structure with placeholders:
    ```sql
    -- BACKFILL_VERSION: 1.0
    -- CHECKPOINT_COLUMNS: project_id, id
    -- DESCRIPTION: Copy completed calls from calls_merged to calls_complete
    
    /*
    Available placeholders (framework provides):
      {db} - target database name
      {batch_size} - current batch size (halves on OOM)
      {checkpoint_<column>} - one per checkpoint_column
      {retry_count} - current retry attempt (0-based)
    
    Migration-specific placeholders (stored in checkpoint_data JSON):
      {cutover_timestamp} - calculated once at backfill start
      {dedup_window_seconds} - configurable per backfill
      ... any other custom params you need
    */
    
    INSERT INTO {db}.target_table
    SELECT ...
    FROM {db}.source_table
    WHERE (column1 > '{checkpoint_column1}')
       OR (column1 = '{checkpoint_column1}' AND column2 > '{checkpoint_column2}')
    ORDER BY column1, column2
    LIMIT {batch_size};
    ```

---

## Phase 2: Backfill Manager Implementation

### 2.1 Core Manager Class

#### Create ClickHouseBackfillManager class
- [ ] Create file: `weave/trace_server/clickhouse_backfill_manager.py`
- [ ] Class structure:
    ```python
    class ClickHouseBackfillManager:
        """
        Manages ClickHouse data backfills with checkpointing and resumability.
        
        Keeps framework logic simple - complex migration logic belongs in SQL templates.
        
        Examples:
            manager = ClickHouseBackfillManager(ch_client)
            
            # List pending backfills
            backfills = manager.list_backfills(database="weave")
            
            # Execute a backfill
            manager.run_backfill(database="weave", version=21)
            
            # Check status
            status = manager.get_status(database="weave", version=21)
        """
        
        def __init__(
            self,
            ch_client: CHClient,
            replicated: Optional[bool] = None,
        ):
            """
            Initialize the backfill manager.
            
            Args:
                ch_client: ClickHouse client instance.
                replicated: Whether to use replicated tables. If None, auto-detect.
            """
            self.ch_client = ch_client
            self.replicated = replicated
            self._initialize_backfill_table()
    ```

---

#### Initialization and discovery
- [ ] Implement `_initialize_backfill_table()` method
  - [ ] Create backfills table if it doesn't exist
  - [ ] Handle replicated mode like migrator does

- [ ] Implement `_discover_backfill_files()` method
  - [ ] Scan migrations directory for `*.backfill.sql` and `*.backfill.meta` files
  - [ ] Parse migration version from filename
  - [ ] Validate both files exist together
  - [ ] Load and parse metadata JSON
  - [ ] Return dict: `{version: {"sql_path": ..., "metadata": ...}}`

- [ ] Implement `_validate_metadata()` method
  - [ ] Check required fields: version, batch_size, checkpoint_columns
  - [ ] Validate types and ranges
  - [ ] Raise clear errors for invalid metadata

---

### 2.2 Checkpoint Management (Keep Simple)

#### Checkpoint as simple JSON dict
```python
# Example checkpoint structure
checkpoint = {
    # Position tracking (from checkpoint_columns)
    "project_id": "abc123",
    "id": "xyz789",
    
    # Progress metrics
    "rows_processed": 1500000,
    "batches_completed": 15,
    
    # State
    "current_batch_size": 1000000,  # May have been reduced from initial
    "started_at": "2024-10-07T10:00:00Z",
    "last_updated": "2024-10-07T11:30:00Z",
    
    # Migration-specific data (calls_complete specific)
    "cutover_timestamp": "2024-01-01T09:00:00",
    "dedup_window_seconds": 3600
}
```

#### Checkpoint operations
- [ ] Implement `_load_checkpoint(backfill_id: str) -> dict` method
  - [ ] Query `db_management.backfills` for checkpoint_data
  - [ ] Parse JSON string to dict
  - [ ] Return empty dict with initial values if not found
  - [ ] Handle malformed JSON gracefully

- [ ] Implement `_save_checkpoint(backfill_id: str, checkpoint: dict) -> None` method
  - [ ] Serialize dict to JSON string
  - [ ] Update `db_management.backfills` row
  - [ ] Update `updated_at` timestamp automatically
  - [ ] Increment `rows_processed` from checkpoint data

- [ ] Implement `_create_initial_checkpoint(metadata: dict) -> dict` method
  - [ ] Initialize checkpoint columns to empty/zero values
  - [ ] Set initial batch_size from metadata
  - [ ] Add timestamp fields
  - [ ] Return initial checkpoint dict

---

### 2.3 Batch Execution (Minimal Logic)

#### SQL rendering
- [ ] Implement `_render_sql(template: str, checkpoint: dict, metadata: dict) -> str` method
  - [ ] Replace `{db}` with database name
  - [ ] Replace `{batch_size}` with current batch size from checkpoint
  - [ ] Replace `{checkpoint_<col>}` for each checkpoint column
  - [ ] Replace any custom variables from checkpoint dict
  - [ ] Use safe parameter substitution (escape strings)
  - [ ] Return rendered SQL

#### Batch execution with simple retry
- [ ] Implement `_execute_batch(sql: str, checkpoint: dict, metadata: dict) -> dict` method
  ```python
  def _execute_batch(self, sql: str, checkpoint: dict, metadata: dict) -> dict:
      """
      Execute a single batch with simple OOM retry logic.
      
      Args:
          sql: Rendered SQL query.
          checkpoint: Current checkpoint state.
          metadata: Backfill metadata.
      
      Returns:
          dict: {"rows_affected": int, "success": bool, "error": Optional[str]}
      """
      batch_size = checkpoint.get('current_batch_size', metadata['batch_size'])
      max_retries = metadata.get('max_retries', 3)
      timeout = metadata.get('timeout_seconds', 3600)
      
      for attempt in range(max_retries):
          try:
              # Re-render SQL with current batch_size
              rendered = sql.replace('{batch_size}', str(batch_size))
              
              # Execute with timeout
              result = self.ch_client.query(
                  rendered, 
                  timeout=timeout,
                  settings={'max_memory_usage': '10000000000'}
              )
              
              # Success!
              checkpoint['current_batch_size'] = batch_size
              return {
                  "rows_affected": result.summary.get('written_rows', 0),
                  "success": True,
                  "error": None
              }
              
          except MemoryError as e:
              # Halve batch size and retry
              batch_size = batch_size // 2
              if batch_size < 1000:
                  return {"rows_affected": 0, "success": False, 
                          "error": f"Batch size too small after retries: {e}"}
              
              logger.warning(f"OOM on attempt {attempt+1}, reducing to {batch_size}")
              checkpoint['current_batch_size'] = batch_size
              continue
              
          except Exception as e:
              logger.error(f"Batch execution failed on attempt {attempt+1}: {e}")
              if attempt == max_retries - 1:
                  return {"rows_affected": 0, "success": False, "error": str(e)}
              time.sleep(2 ** attempt)  # Exponential backoff
      
      return {"rows_affected": 0, "success": False, "error": "Max retries exceeded"}
  ```

#### Main execution loop
- [ ] Implement `run_backfill(database: str, version: int, max_batches: Optional[int] = None)` method
  ```python
  def run_backfill(self, database: str, version: int, max_batches: Optional[int] = None):
      """
      Execute a backfill from current checkpoint to completion.
      
      Args:
          database: Target database name.
          version: Migration version number.
          max_batches: Optional limit for testing/debugging.
      """
      backfill_id = f"{database}_{version}"
      
      # Load metadata and SQL template
      backfill = self._discover_backfill_files().get(version)
      if not backfill:
          raise ValueError(f"No backfill found for version {version}")
      
      sql_template = Path(backfill['sql_path']).read_text()
      metadata = backfill['metadata']
      
      # Load or create checkpoint
      checkpoint = self._load_checkpoint(backfill_id)
      if not checkpoint:
          checkpoint = self._create_initial_checkpoint(metadata)
          self._register_backfill(backfill_id, database, version, metadata)
      
      # Update status to running
      self._update_status(backfill_id, 'running')
      
      try:
          batch_num = checkpoint.get('batches_completed', 0)
          
          while True:
              if max_batches and batch_num >= max_batches:
                  break
              
              # Render SQL with current checkpoint
              sql = self._render_sql(sql_template, checkpoint, metadata)
              
              # Execute batch
              result = self._execute_batch(sql, checkpoint, metadata)
              
              if not result['success']:
                  self._update_status(backfill_id, 'failed')
                  raise RuntimeError(f"Batch execution failed: {result['error']}")
              
              # Check if complete
              if result['rows_affected'] == 0:
                  self._update_status(backfill_id, 'completed')
                  logger.info(f"Backfill {backfill_id} completed!")
                  break
              
              # Update checkpoint
              checkpoint['rows_processed'] += result['rows_affected']
              checkpoint['batches_completed'] = batch_num + 1
              checkpoint['last_updated'] = datetime.now(timezone.utc).isoformat()
              
              # Get new checkpoint position (query target table for max values)
              new_position = self._get_last_inserted_position(
                  database, 
                  metadata['target_table'] if 'target_table' in metadata else None,
                  metadata['checkpoint_columns']
              )
              checkpoint.update(new_position)
              
              # Save checkpoint
              self._save_checkpoint(backfill_id, checkpoint)
              
              logger.info(f"Batch {batch_num + 1}: {result['rows_affected']} rows, "
                         f"total: {checkpoint['rows_processed']}")
              
              batch_num += 1
              
      except KeyboardInterrupt:
          logger.info(f"Backfill interrupted, checkpoint saved at batch {batch_num}")
          self._update_status(backfill_id, 'paused')
          raise
  ```

- [ ] Implement `_get_last_inserted_position(db: str, table: str, columns: list) -> dict` method
  - [ ] Query target table for MAX() of each checkpoint column
  - [ ] Return dict with column values for next checkpoint
  - [ ] Handle NULL values appropriately

---

### 2.4 Status and Control

#### Status tracking
- [ ] Implement `get_status(database: str, version: int) -> dict` method
  - [ ] Query backfills table
  - [ ] Parse checkpoint_data JSON
  - [ ] Calculate progress percentage if possible
  - [ ] Return structured dict with all status info

- [ ] Implement `list_backfills(database: Optional[str] = None, status: Optional[str] = None) -> list[dict]` method
  - [ ] Query backfills table with filters
  - [ ] Return list of status dicts

- [ ] Implement `_update_status(backfill_id: str, status: str) -> None` method
  - [ ] Update status column in backfills table
  - [ ] Set completed_at if status is 'completed'

#### Control operations
- [ ] Implement `pause_backfill(database: str, version: int) -> None` method
  - [ ] Update status to 'paused'
  - [ ] Log current checkpoint

- [ ] Implement `resume_backfill(database: str, version: int) -> None` method
  - [ ] Check current status is 'paused' or 'failed'
  - [ ] Call run_backfill() to continue from checkpoint

---

## Phase 3: CLI Interface

### 3.1 Create CLI Module

- [ ] Create file: `weave/trace_server/backfill_cli.py`
- [ ] Use Click or argparse for CLI framework

#### Implement core commands

**list command**:
```bash
python -m weave.trace_server.backfill list [--database=weave] [--status=pending]
```
- [ ] Show table: Version | Description | Status | Progress | Rows | Started | Updated

**run command**:
```bash
python -m weave.trace_server.backfill run --database=weave --version=21 [--max-batches=10]
```
- [ ] Initialize if needed
- [ ] Execute backfill loop
- [ ] Handle Ctrl+C gracefully
- [ ] Options: `--max-batches` for testing, `--batch-size` to override default

**status command**:
```bash
python -m weave.trace_server.backfill status --database=weave --version=21
```
- [ ] Show detailed status: checkpoint position, rows processed, current batch size, etc.
- [ ] Display last error if failed

**pause command**:
```bash
python -m weave.trace_server.backfill pause --database=weave --version=21
```
- [ ] Update status to paused
- [ ] Show current checkpoint

**resume command**:
```bash
python -m weave.trace_server.backfill resume --database=weave --version=21
```
- [ ] Continue from last checkpoint
- [ ] Same as `run` but with status validation

---

## Phase 4: Integration with Migration System

### 4.1 Migration Discovery

- [ ] Update `ClickHouseTraceServerMigrator` to check for backfills after applying migrations
  ```python
  def apply_migrations(self, target_db: str, target_version: Optional[int] = None) -> None:
      # ... existing migration logic ...
      
      # Register any new backfills
      backfill_manager = ClickHouseBackfillManager(self.ch_client)
      backfill_manager.register_pending_backfills(
          db_name=target_db,
          migration_versions=newly_applied_versions
      )
  ```

- [ ] Implement `register_pending_backfills(db_name: str, migration_versions: list[int])` method
  - [ ] For each version, check if `.backfill.sql` exists
  - [ ] Load metadata
  - [ ] Create row in backfills table with status='pending'
  - [ ] If `run_on_startup=true`, execute inline (for small backfills)
  - [ ] Otherwise log: "Backfill registered, run with CLI"

---

## Phase 5: Testing

### 5.1 Unit Tests

- [ ] Create `tests/trace_server/test_backfill_manager.py`
- [ ] Test checkpoint save/load with various data types
- [ ] Test SQL rendering with different checkpoint columns
- [ ] Test batch size reduction on OOM
- [ ] Test metadata validation

### 5.2 Integration Tests

- [ ] Create `tests/trace_server/test_backfill_integration.py`
- [ ] Start local ClickHouse (Docker)
- [ ] Test full backfill lifecycle: register → run → pause → resume → complete
- [ ] Test interruption and recovery
- [ ] Test with multiple batches

---

## Phase 6: Specific Migration - calls_complete Backfill

### 6.1 Create Schema

- [ ] Create file: `migrations/021_calls_complete.up.sql`
  ```sql
  CREATE TABLE IF NOT EXISTS {db}.calls_complete (
      project_id String,
      id String,
      trace_id String,
      parent_id Nullable(String),
      thread_id Nullable(String),
      turn_id Nullable(String),
      op_name String,
      display_name Nullable(String),
      started_at DateTime64(3),
      ended_at DateTime64(3),  -- NOT NULL, only completed calls
      exception Nullable(String),
      attributes_dump Nullable(String),
      inputs_dump Nullable(String),
      output_dump Nullable(String),
      summary_dump Nullable(String),
      input_refs Array(String),
      output_refs Array(String),
      wb_user_id Nullable(String),
      wb_run_id Nullable(String),
      wb_run_step Nullable(Int64),
      wb_run_step_end Nullable(Int64)
  ) ENGINE = MergeTree
  ORDER BY (project_id, id);
  ```

- [ ] Create file: `migrations/021_calls_complete.down.sql`
  ```sql
  DROP TABLE IF EXISTS {db}.calls_complete;
  ```

---

### 6.2 Create Backfill Metadata

- [ ] Create file: `migrations/021_calls_complete.backfill.meta`
  ```json
  {
    "migration_version": 21,
    "description": "Backfill calls_complete from calls_merged with completed calls only",
    "batch_size": 1000000,
    "checkpoint_columns": ["project_id", "id"],
    "timeout_seconds": 3600,
    "run_on_startup": false,
    "max_retries": 3
  }
  ```

---

### 6.3 Create Backfill SQL with Migration-Specific Logic

- [ ] Create file: `migrations/021_calls_complete.backfill.sql`
  ```sql
  -- BACKFILL_VERSION: 1.0
  -- CHECKPOINT_COLUMNS: project_id, id
  -- DESCRIPTION: Backfill calls_complete from calls_merged
  
  /*
  MIGRATION-SPECIFIC COMPLEXITY (not framework):
  
  1. AggregatingMergeTree Handling:
     - calls_merged stores aggregate state columns
     - MUST use GROUP BY with -Merge functions to finalize
  
  2. Index-Friendly Batching:
     - LIMIT raw rows BEFORE GROUP BY to use (project_id, id) index
     - Find last complete (project_id, id) to avoid partial groups
     - Batch size will dynamically reduce on OOM (framework handles this)
  
  3. Cutover Timestamp:
     - Only backfill calls before cutover_timestamp
     - Calculated once at start: MIN(started_at) - 1 hour safety margin
     - Everything after cutover is handled by new write path
  
  4. Deduplication Near Cutover:
     - Check calls_complete for existing records near cutover boundary
     - Skip check for older calls (performance optimization)
  
  Framework provides: {db}, {batch_size}, {checkpoint_project_id}, {checkpoint_id}
  Checkpoint data provides: {cutover_timestamp}, {dedup_window_seconds}
  */
  
  WITH raw_batch AS (
      -- Step 1: LIMIT raw rows BEFORE GROUP BY (uses index efficiently)
      SELECT *
      FROM {db}.calls_merged
      WHERE (project_id > '{checkpoint_project_id}' 
             OR (project_id = '{checkpoint_project_id}' AND id > '{checkpoint_id}'))
      ORDER BY project_id, id, sortable_datetime
      LIMIT {batch_size}
  ),
  complete_groups AS (
      -- Step 2: Identify all complete (project_id, id) groups in batch
      SELECT project_id, id
      FROM raw_batch
      GROUP BY project_id, id
  ),
  last_complete AS (
      -- Step 3: Find last complete group to avoid partial data
      SELECT project_id, id
      FROM complete_groups
      ORDER BY project_id DESC, id DESC
      LIMIT 1
  ),
  aggregated_calls AS (
      -- Step 4: Aggregate with business logic filters
      SELECT 
          cm.project_id,
          cm.id,
          anyMerge(cm.trace_id) as trace_id,
          anyMerge(cm.parent_id) as parent_id,
          anyMerge(cm.thread_id) as thread_id,
          anyMerge(cm.turn_id) as turn_id,
          anyMerge(cm.op_name) as op_name,
          argMaxMerge(cm.display_name) as display_name,
          anyMerge(cm.started_at) as started_at,
          anyMerge(cm.ended_at) as ended_at,
          anyMerge(cm.exception) as exception,
          anyMerge(cm.attributes_dump) as attributes_dump,
          anyMerge(cm.inputs_dump) as inputs_dump,
          anyMerge(cm.output_dump) as output_dump,
          anyMerge(cm.summary_dump) as summary_dump,
          array_concat_aggMerge(cm.input_refs) as input_refs,
          array_concat_aggMerge(cm.output_refs) as output_refs,
          anyMerge(cm.wb_user_id) as wb_user_id,
          anyMerge(cm.wb_run_id) as wb_run_id,
          anyMerge(cm.wb_run_step) as wb_run_step,
          anyMerge(cm.wb_run_step_end) as wb_run_step_end
      FROM {db}.calls_merged cm
      WHERE (cm.project_id, cm.id) IN (SELECT project_id, id FROM complete_groups)
        AND (cm.project_id < (SELECT project_id FROM last_complete)
             OR (cm.project_id = (SELECT project_id FROM last_complete) 
                 AND cm.id <= (SELECT id FROM last_complete)))
      GROUP BY cm.project_id, cm.id
      HAVING anyMerge(ended_at) IS NOT NULL  -- Only completed calls
         AND anyMerge(started_at) < toDateTime64('{cutover_timestamp}', 3)  -- Before cutover
  ),
  dedup_check AS (
      -- Step 5: Check for duplicates only near cutover boundary
      SELECT ac.project_id, ac.id
      FROM aggregated_calls ac
      WHERE ac.started_at < toDateTime64('{cutover_timestamp}', 3) - INTERVAL {dedup_window_seconds} SECOND
         OR NOT EXISTS (
              SELECT 1 FROM {db}.calls_complete cc
              WHERE cc.project_id = ac.project_id AND cc.id = ac.id
         )
  )
  INSERT INTO {db}.calls_complete
  SELECT * FROM aggregated_calls
  WHERE (project_id, id) IN (SELECT project_id, id FROM dedup_check)
  ORDER BY project_id, id;
  ```

**Key points**:
- All the complexity is self-contained in the SQL
- Framework just replaces variables and executes
- Cutover and dedup logic is migration-specific, not framework-level
- Comments explain the "why" for future maintainers

---

### 6.4 Initialize Cutover Timestamp

When backfill starts for the first time, calculate cutover once:

- [ ] Add logic in `_create_initial_checkpoint()` to detect if SQL needs cutover_timestamp
- [ ] If needed, execute query:
  ```sql
  SELECT dateAdd(HOUR, -1, MIN(anyMerge(started_at))) as cutover
  FROM {db}.calls_merged
  ```
- [ ] Store in checkpoint_data:
  ```json
  {
    "project_id": "",
    "id": "",
    "cutover_timestamp": "2024-01-01T08:00:00",
    "dedup_window_seconds": 3600,
    "current_batch_size": 1000000,
    "rows_processed": 0,
    "batches_completed": 0
  }
  ```

---

### 6.5 Validation

After backfill completes:

- [ ] Run validation query:
  ```sql
  -- Count source (completed calls in calls_merged)
  SELECT count(*) as source_count
  FROM (
      SELECT project_id, id
      FROM calls_merged
      GROUP BY project_id, id
      HAVING anyMerge(ended_at) IS NOT NULL
         AND anyMerge(started_at) < toDateTime64('{cutover_timestamp}', 3)
  );
  
  -- Count target
  SELECT count(*) as target_count
  FROM calls_complete;
  
  -- Should match!
  ```

- [ ] Spot-check sample records for data correctness
- [ ] Verify no duplicates: `SELECT project_id, id, count(*) FROM calls_complete GROUP BY project_id, id HAVING count(*) > 1`

---

## Phase 7: Documentation

### 7.1 User Documentation

- [ ] Create `docs/backfill_runbook.md`:
  - How to check for pending backfills
  - How to run a backfill
  - How to monitor progress
  - What to do if it fails
  - How to resume after failure

### 7.2 Developer Documentation

- [ ] Create `docs/backfill_developer_guide.md`:
  - When to use backfills vs inline migrations
  - How to write backfill SQL and metadata
  - How checkpoint columns work
  - Example simple backfill
  - Example complex backfill (calls_complete)
  - Testing locally

### 7.3 Code Documentation

- [ ] Add Google-style docstrings to all public methods
- [ ] Add inline comments explaining non-obvious logic
- [ ] Document the checkpoint JSON structure

---

## Phase 8: Deployment

### 8.1 Development

- [ ] Test with local ClickHouse
- [ ] Create dummy backfill for testing
- [ ] Verify CLI commands
- [ ] Test interrupt and resume

### 8.2 Staging

- [ ] Deploy migration 020 (backfill infrastructure)
- [ ] Deploy migration 021 (calls_complete + backfill)
- [ ] Verify backfill is registered
- [ ] Run with `--max-batches=10` to test
- [ ] Run full backfill
- [ ] Validate results

### 8.3 Production

- [ ] Deploy migrations
- [ ] Check backfill status: `python -m weave.trace_server.backfill list --database=weave`
- [ ] Start backfill: `python -m weave.trace_server.backfill run --database=weave --version=21`
- [ ] Monitor progress periodically
- [ ] Validate on completion

---

## Estimated Timeline

- **Phase 1 (Schema)**: 0.5 days
- **Phase 2 (Manager)**: 2-3 days
- **Phase 3 (CLI)**: 1 day
- **Phase 4 (Integration)**: 0.5 days
- **Phase 5 (Tests)**: 1-2 days
- **Phase 6 (calls_complete migration)**: 2 days
- **Phase 7 (Docs)**: 1 day
- **Phase 8 (Deploy)**: 1 day

**Total: ~8-10 days** (down from 2-3 weeks)

---

## Success Criteria

### Functional
- ✅ Can backfill calls_complete from calls_merged successfully
- ✅ Handles interruption and resumes without data loss
- ✅ Processes millions of rows without timeout
- ✅ Batch size automatically reduces on OOM
- ✅ Accurate progress tracking

### Code Quality
- ✅ Manager class < 500 lines of code (simple!)
- ✅ All public methods have docstrings
- ✅ Unit and integration tests pass
- ✅ No complex error handling hierarchies
- ✅ Framework is reusable for future backfills

### Operational
- ✅ CLI works as expected
- ✅ Documentation explains how to use
- ✅ Can monitor progress easily
- ✅ Future engineers can add backfills without framework changes

---

## Key Design Principles

1. **Simplicity First**: Keep framework minimal, put complexity in SQL
2. **Checkpoint Everything**: Always save progress before failing
3. **Fail Loudly**: Log errors clearly, don't hide problems
4. **SQL Owns Logic**: Migration-specific logic stays in SQL template
5. **JSON for Flexibility**: Checkpoint data is unstructured dict/JSON
6. **No Premature Optimization**: Start simple, optimize later if needed

---

## Notes

### What We Removed (Complexity Reduction)

- ❌ Separate error tracking table (use log files)
- ❌ Checkpoint snapshots table (use current checkpoint only)
- ❌ Complex error classification (just retry and fail)
- ❌ Circuit breakers (max_retries is enough)
- ❌ Custom exception types (use standard exceptions)
- ❌ Dataclasses for state (use dicts)
- ❌ Binary search for bad rows (just fail the batch)
- ❌ Progress estimation with ETA (nice-to-have)
- ❌ Validation queries in metadata (run manually)
- ❌ Priority queue for backfills (process sequentially)
- ❌ Adaptive batch sizing (just halve on OOM)
- ❌ Separate cutover config in framework (migration-specific)

### What We Kept (Essential)

- ✅ Single tracking table
- ✅ Checkpoint save/load
- ✅ Batch execution loop
- ✅ Simple OOM retry (halve batch size)
- ✅ Status tracking (pending/running/completed/failed/paused)
- ✅ Basic CLI (list, run, status, pause, resume)
- ✅ Migration integration

---

**Last Updated**: 2024-10-07  
**Status**: Ready for Implementation