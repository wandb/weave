-- Migration 027: Add TTL support for per-project call data retention
--
-- Safe to deploy alone — all rows get the 2100-01-01 sentinel, nothing expires
-- until a user explicitly configures TTL via the API.

-- Step 1: Create project_ttl_settings table
-- Stores the per-project retention duration as an append-only audit trail.
-- Use argMax(retention_days, updated_at) to read the latest setting.
-- retention_days = 0 means "no TTL" (infinite retention).
CREATE TABLE project_ttl_settings (
    project_id      String,
    retention_days  Int32,
    updated_at      DateTime64(3) DEFAULT now64(3),
    updated_by      String DEFAULT ''
) ENGINE = MergeTree()
ORDER BY (project_id, updated_at)
SETTINGS
    enable_block_number_column = 1,
    enable_block_offset_column = 1;

-- Step 1b: Rename existing ttl_at column on calls_complete (created by migration 024) to expire_at
ALTER TABLE calls_complete RENAME COLUMN ttl_at TO expire_at;

-- Step 2: Add expire_at to call_parts (v1 raw storage)
ALTER TABLE call_parts
    ADD COLUMN expire_at DateTime64(3) DEFAULT toDateTime64('2100-01-01 00:00:00', 3);

-- Step 3: Add expire_at to calls_merged (v1 aggregated table)
ALTER TABLE calls_merged
    ADD COLUMN expire_at SimpleAggregateFunction(min, DateTime64(3))
    DEFAULT toDateTime64('2100-01-01 00:00:00', 3);

-- Step 4: Update calls_merged_view to propagate expire_at from call_parts
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
        minSimpleState(expire_at) as expire_at
    FROM call_parts
    GROUP BY project_id,
        id;

-- Step 5: Enable TTL deletion on calls_merged
ALTER TABLE calls_merged MODIFY TTL expire_at DELETE;

-- Step 6: Enable TTL deletion on call_parts
ALTER TABLE call_parts MODIFY TTL expire_at DELETE;

-- Step 7: Add expire_at column and TTL to calls_merged_stats
ALTER TABLE calls_merged_stats
    ADD COLUMN IF NOT EXISTS expire_at SimpleAggregateFunction(min, DateTime64(3))
    DEFAULT toDateTime64('2100-01-01 00:00:00', 3);

ALTER TABLE calls_merged_stats MODIFY TTL expire_at DELETE;

-- Step 8: Add expire_at column and TTL to calls_complete_stats
ALTER TABLE calls_complete_stats
    ADD COLUMN IF NOT EXISTS expire_at SimpleAggregateFunction(min, DateTime64(3))
    DEFAULT toDateTime64('2100-01-01 00:00:00', 3);

-- IMPORTANT: `calls_complete` has had `source` since v2, but `calls_complete_stats` missed the matching aggregate column.
-- Fix it here so existing deployments pick it up during this upgrade, then populate it from `calls_complete.source` below.
ALTER TABLE calls_complete_stats
    ADD COLUMN IF NOT EXISTS source SimpleAggregateFunction(any, Enum8('direct' = 1, 'dual' = 2, 'migration' = 3))
    DEFAULT 'direct';

ALTER TABLE calls_complete_stats MODIFY TTL expire_at DELETE;

-- Step 9: Update calls_merged_stats_view to propagate expire_at
ALTER TABLE calls_merged_stats_view MODIFY QUERY
SELECT
    call_parts.project_id,
    call_parts.id,
    anySimpleState(call_parts.trace_id) as trace_id,
    anySimpleState(call_parts.parent_id) as parent_id,
    anySimpleState(call_parts.thread_id) as thread_id,
    anySimpleState(call_parts.turn_id) as turn_id,
    anySimpleState(call_parts.op_name) as op_name,
    anySimpleState(call_parts.started_at) as started_at,
    anySimpleState(length(call_parts.attributes_dump)) as attributes_size_bytes,
    anySimpleState(length(call_parts.inputs_dump)) as inputs_size_bytes,
    anySimpleState(call_parts.ended_at) as ended_at,
    anySimpleState(length(call_parts.output_dump)) as output_size_bytes,
    anySimpleState(length(call_parts.summary_dump)) as summary_size_bytes,
    anySimpleState(length(call_parts.exception)) as exception_size_bytes,
    anySimpleState(call_parts.wb_user_id) as wb_user_id,
    anySimpleState(call_parts.wb_run_id) as wb_run_id,
    anySimpleState(call_parts.wb_run_step) as wb_run_step,
    anySimpleState(call_parts.wb_run_step_end) as wb_run_step_end,
    anySimpleState(call_parts.deleted_at) as deleted_at,
    maxSimpleState(call_parts.created_at) as updated_at,
    argMaxState(call_parts.display_name, call_parts.created_at) as display_name,
    anySimpleState(length(call_parts.otel_dump)) as otel_dump_size_bytes,
    minSimpleState(call_parts.expire_at) as expire_at
FROM call_parts
GROUP BY
    call_parts.project_id,
    call_parts.id;

-- Step 10: Update calls_complete_stats_view to propagate expire_at
ALTER TABLE calls_complete_stats_view MODIFY QUERY
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
    anySimpleState(calls_complete.source) as source,
    minSimpleState(calls_complete.created_at) as created_at,
    maxSimpleState(calls_complete.updated_at) as updated_at,
    argMaxState(calls_complete.display_name, calls_complete.created_at) as display_name,
    minSimpleState(calls_complete.expire_at) as expire_at
FROM calls_complete
GROUP BY
    calls_complete.project_id,
    calls_complete.id;
