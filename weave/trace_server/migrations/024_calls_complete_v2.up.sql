-- Migration: calls_complete v2
-- Changes:
--   1. Remove all Nullable(String) columns, use empty string sentinel for None
--   2. Remove Nullable(DateTime64) columns, use epoch zero sentinel for None
--   3. Switch from MergeTree to ReplacingMergeTree(created_at)
--   4. Partition by month on started_at
--   5. Add TTL DELETE by ttl_at
--   6. Add new columns: ttl_at, source (Enum8)
--   7. Add bloom filter index on summary_dump
--   8. Add table-level settings: min_bytes_for_wide_part=0
--
-- Migration procedure:
--   Step 1: Create new table calls_complete_new
--   Step 2: Create materialized view to sync live inserts
--   Step 3: Backfill from old table
--   Step 4: Drop old stats view/table, drop migration view, rename tables
--   Step 5: Recreate stats table and materialized view

-- Step 1: Create new table
CREATE TABLE calls_complete_new (
    -- Primary fields
    id              String,
    project_id      String,
    created_at      DateTime64(3) DEFAULT now64(3),
    trace_id        String,
    op_name         String,
    started_at      DateTime64(6),

    -- DateTime fields: sentinel = epoch zero (toDateTime64(0, N))
    ended_at        DateTime64(6) DEFAULT toDateTime64(0, 6),
    updated_at      DateTime64(3) DEFAULT toDateTime64(0, 3),
    deleted_at      DateTime64(3) DEFAULT toDateTime64(0, 3),

    -- String fields: sentinel = '' (empty string)
    parent_id       String DEFAULT '',
    display_name    String DEFAULT '',
    exception       String DEFAULT '',
    otel_dump       String DEFAULT '',
    wb_user_id      String DEFAULT '',
    wb_run_id       String DEFAULT '',
    thread_id       String DEFAULT '',
    turn_id         String DEFAULT '',

    -- Non-nullable data fields (unchanged)
    inputs_dump     String,
    input_refs      Array(String),
    output_dump     String,
    summary_dump    String,
    output_refs     Array(String),

    -- attributes_dump stays as String (not converted to JSON)
    attributes_dump String,

    -- UInt64 fields remain Nullable (punted)
    wb_run_step     Nullable(UInt64),
    wb_run_step_end Nullable(UInt64),

    -- New columns
    ttl_at          DateTime DEFAULT '2050-01-01 00:00:00',
    source          Enum8('direct' = 1, 'dual' = 2, 'migration' = 3) DEFAULT 'direct',

    -- Indexes (carried forward from v1 + new)
    INDEX idx_parent_id parent_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_inputs_dump inputs_dump TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    INDEX idx_output_dump output_dump TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    -- New: bloom filter on summary_dump
    INDEX idx_summary_dump summary_dump TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    INDEX idx_wb_run_id wb_run_id TYPE set(100) GRANULARITY 4,
    INDEX idx_thread_id thread_id TYPE set(100) GRANULARITY 4,
    INDEX idx_op_name op_name TYPE ngrambf_v1(8, 10000, 3, 0) GRANULARITY 1,
    INDEX idx_ended_at ended_at TYPE minmax GRANULARITY 1,
    INDEX idx_id id TYPE minmax GRANULARITY 1
) ENGINE = ReplacingMergeTree(created_at)
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, started_at, id)
TTL ttl_at DELETE
SETTINGS
    min_bytes_for_wide_part=0,
    enable_block_number_column=1,
    enable_block_offset_column=1;


-- Step 2: Create materialized view for live sync during migration
-- This captures any inserts to the old table while backfill is running.
CREATE MATERIALIZED VIEW calls_complete_migration_view
TO calls_complete_new
AS
SELECT
    id,
    project_id,
    created_at,
    trace_id,
    op_name,
    started_at,
    COALESCE(ended_at, toDateTime64(0, 6)) AS ended_at,
    COALESCE(updated_at, toDateTime64(0, 3)) AS updated_at,
    COALESCE(deleted_at, toDateTime64(0, 3)) AS deleted_at,
    COALESCE(parent_id, '') AS parent_id,
    COALESCE(display_name, '') AS display_name,
    COALESCE(exception, '') AS exception,
    COALESCE(otel_dump, '') AS otel_dump,
    COALESCE(wb_user_id, '') AS wb_user_id,
    COALESCE(wb_run_id, '') AS wb_run_id,
    COALESCE(thread_id, '') AS thread_id,
    COALESCE(turn_id, '') AS turn_id,
    inputs_dump,
    input_refs,
    output_dump,
    summary_dump,
    output_refs,
    attributes_dump,
    wb_run_step,
    wb_run_step_end,
    toDateTime('2050-01-01 00:00:00') AS ttl_at,
    'direct' AS source
FROM calls_complete;


-- Step 3: Backfill existing data from old table to new table
INSERT INTO calls_complete_new
SELECT
    id,
    project_id,
    created_at,
    trace_id,
    op_name,
    started_at,
    COALESCE(ended_at, toDateTime64(0, 6)) AS ended_at,
    COALESCE(updated_at, toDateTime64(0, 3)) AS updated_at,
    COALESCE(deleted_at, toDateTime64(0, 3)) AS deleted_at,
    COALESCE(parent_id, '') AS parent_id,
    COALESCE(display_name, '') AS display_name,
    COALESCE(exception, '') AS exception,
    COALESCE(otel_dump, '') AS otel_dump,
    COALESCE(wb_user_id, '') AS wb_user_id,
    COALESCE(wb_run_id, '') AS wb_run_id,
    COALESCE(thread_id, '') AS thread_id,
    COALESCE(turn_id, '') AS turn_id,
    inputs_dump,
    input_refs,
    output_dump,
    summary_dump,
    output_refs,
    attributes_dump,
    wb_run_step,
    wb_run_step_end,
    toDateTime('2050-01-01 00:00:00') AS ttl_at,
    'direct' AS source
FROM calls_complete;


-- Step 4: Drop old stats infrastructure, drop migration view, rename tables
DROP VIEW IF EXISTS calls_complete_stats_view;
DROP TABLE IF EXISTS calls_complete_stats;
DROP VIEW IF EXISTS calls_complete_migration_view;
RENAME TABLE calls_complete TO calls_complete_old;
RENAME TABLE calls_complete_new TO calls_complete;


-- Step 5: Recreate stats table with updated types (non-nullable where changed)
CREATE TABLE calls_complete_stats
(
    project_id String,
    id String,
    trace_id SimpleAggregateFunction(any, String),
    parent_id SimpleAggregateFunction(any, String),
    op_name SimpleAggregateFunction(any, String),
    started_at SimpleAggregateFunction(any, DateTime64(6)),
    ended_at SimpleAggregateFunction(any, DateTime64(6)),
    attributes_size_bytes SimpleAggregateFunction(any, UInt64),
    inputs_size_bytes SimpleAggregateFunction(any, UInt64),
    output_size_bytes SimpleAggregateFunction(any, UInt64),
    summary_size_bytes SimpleAggregateFunction(any, UInt64),
    otel_size_bytes SimpleAggregateFunction(any, UInt64),
    exception_size_bytes SimpleAggregateFunction(any, UInt64),
    wb_user_id SimpleAggregateFunction(any, String),
    wb_run_id SimpleAggregateFunction(any, String),
    wb_run_step SimpleAggregateFunction(any, Nullable(UInt64)),
    wb_run_step_end SimpleAggregateFunction(any, Nullable(UInt64)),
    thread_id SimpleAggregateFunction(any, String),
    turn_id SimpleAggregateFunction(any, String),
    created_at SimpleAggregateFunction(min, DateTime64(3)),
    updated_at SimpleAggregateFunction(max, DateTime64(3)),
    display_name AggregateFunction(argMax, String, DateTime64(3))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, id);

CREATE MATERIALIZED VIEW calls_complete_stats_view
TO calls_complete_stats
AS
SELECT
    calls_complete.project_id,
    calls_complete.id,
    anySimpleState(calls_complete.trace_id) as trace_id,
    anySimpleState(calls_complete.parent_id) as parent_id,
    anySimpleState(calls_complete.op_name) as op_name,
    anySimpleState(calls_complete.started_at) as started_at,
    anySimpleState(calls_complete.ended_at) as ended_at,
    anySimpleState(length(calls_complete.attributes_dump)) as attributes_size_bytes,
    anySimpleState(length(calls_complete.inputs_dump)) as inputs_size_bytes,
    anySimpleState(length(calls_complete.output_dump)) as output_size_bytes,
    anySimpleState(length(calls_complete.summary_dump)) as summary_size_bytes,
    anySimpleState(length(calls_complete.exception)) as exception_size_bytes,
    anySimpleState(length(calls_complete.otel_dump)) as otel_size_bytes,
    anySimpleState(calls_complete.wb_user_id) as wb_user_id,
    anySimpleState(calls_complete.wb_run_id) as wb_run_id,
    anySimpleState(calls_complete.wb_run_step) as wb_run_step,
    anySimpleState(calls_complete.wb_run_step_end) as wb_run_step_end,
    anySimpleState(calls_complete.thread_id) as thread_id,
    anySimpleState(calls_complete.turn_id) as turn_id,
    minSimpleState(calls_complete.created_at) as created_at,
    maxSimpleState(calls_complete.updated_at) as updated_at,
    argMaxState(calls_complete.display_name, calls_complete.created_at) as display_name
FROM calls_complete
GROUP BY
    calls_complete.project_id,
    calls_complete.id;
