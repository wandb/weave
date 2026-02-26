-- Migration 025: Add TTL support for per-project call data retention
--
-- Safe to deploy alone — all rows get the 2100-01-01 sentinel, nothing expires
-- until a user explicitly configures TTL via the API.

-- Step 1: Create project_ttl_settings table
-- Stores the per-project retention duration. Uses ReplacingMergeTree(updated_at)
-- so upserts naturally resolve to the latest setting.
-- retention_days = 0 means "no TTL" (infinite retention).
CREATE TABLE project_ttl_settings (
    project_id      String,
    retention_days  UInt32,
    updated_at      DateTime64(3) DEFAULT now64(3),
    updated_by      String DEFAULT ''
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (project_id)
SETTINGS
    enable_block_number_column = 1,
    enable_block_offset_column = 1;

-- Step 2: Add ttl_at to call_parts (v1 raw storage)
ALTER TABLE call_parts
    ADD COLUMN ttl_at DateTime DEFAULT '2100-01-01 00:00:00';

-- Step 3: Add ttl_at to calls_merged (v1 aggregated table)
ALTER TABLE calls_merged
    ADD COLUMN ttl_at SimpleAggregateFunction(min, DateTime)
    DEFAULT '2100-01-01 00:00:00';

-- Step 4: Update calls_merged_view to propagate ttl_at from call_parts
ALTER TABLE calls_merged_view MODIFY QUERY
    SELECT project_id,
        id,
        anySimpleState(wb_run_id) as wb_run_id,
        anySimpleState(wb_run_step) as wb_run_step,
        anySimpleState(wb_run_step_end) as wb_run_step_end,
        anySimpleStateIf(wb_user_id, isNotNull(call_parts.started_at)) as wb_user_id,
        anySimpleState(trace_id) as trace_id,
        anySimpleState(parent_id) as parent_id,
        anySimpleState(thread_id) as thread_id,
        anySimpleState(turn_id) as turn_id,
        anySimpleState(op_name) as op_name,
        anySimpleState(started_at) as started_at,
        anySimpleState(attributes_dump) as attributes_dump,
        anySimpleState(inputs_dump) as inputs_dump,
        array_concat_aggSimpleState(input_refs) as input_refs,
        anySimpleState(ended_at) as ended_at,
        anySimpleState(output_dump) as output_dump,
        anySimpleState(summary_dump) as summary_dump,
        anySimpleState(exception) as exception,
        array_concat_aggSimpleState(output_refs) as output_refs,
        anySimpleState(deleted_at) as deleted_at,
        argMaxState(display_name, call_parts.created_at) as display_name,
        anySimpleState(coalesce(call_parts.started_at, call_parts.ended_at, call_parts.created_at)) as sortable_datetime,
        anySimpleState(otel_dump) as otel_dump,
        minSimpleState(ttl_at) as ttl_at
    FROM call_parts
    GROUP BY project_id,
        id;

-- Step 5: Enable TTL deletion on calls_merged
ALTER TABLE calls_merged MODIFY TTL ttl_at DELETE;

-- Step 6: Enable TTL deletion on call_parts
ALTER TABLE call_parts MODIFY TTL ttl_at DELETE;
