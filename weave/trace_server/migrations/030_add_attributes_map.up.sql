-- Migration 030: Add typed attribute maps for fast filtering.
--
-- Adds four Map columns alongside attributes_dump on call_parts, calls_merged,
-- and calls_complete. The typed maps are populated at ingest from the Python
-- attributes dict by dispatching each value to the map matching its type.
-- Read-path filters with a known type (via $convert) hit the typed map
-- directly instead of JSON_VALUE over attributes_dump.
--
-- attributes_dump is preserved; typed maps are a duplicated read-path index.
-- Existing rows get empty maps by default and continue to work via the
-- JSON_VALUE fallback.

-- Step 1: Add typed maps to call_parts. Map columns default to empty map in
-- ClickHouse, so no explicit DEFAULT clause is needed.
ALTER TABLE call_parts
    ADD COLUMN attributes_map_str   Map(String, String),
    ADD COLUMN attributes_map_int   Map(String, Int64),
    ADD COLUMN attributes_map_float Map(String, Float64),
    ADD COLUMN attributes_map_bool  Map(String, Bool);

-- Step 2: Add typed maps to calls_merged as SimpleAggregateFunction(any, ...)
-- to match the existing AMT aggregation pattern.
ALTER TABLE calls_merged
    ADD COLUMN attributes_map_str   SimpleAggregateFunction(any, Map(String, String)),
    ADD COLUMN attributes_map_int   SimpleAggregateFunction(any, Map(String, Int64)),
    ADD COLUMN attributes_map_float SimpleAggregateFunction(any, Map(String, Float64)),
    ADD COLUMN attributes_map_bool  SimpleAggregateFunction(any, Map(String, Bool));

-- Step 3: Propagate typed maps through calls_merged_view.
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
        -- Maps default to map() on non-start rows. Gate on isNotNull(started_at)
        -- so the empty default from an end/delete/update row can't win over
        -- the start row's populated maps under SimpleAggregateFunction(any).
        anySimpleStateIf(attributes_map_str, isNotNull(call_parts.started_at)) as attributes_map_str,
        anySimpleStateIf(attributes_map_int, isNotNull(call_parts.started_at)) as attributes_map_int,
        anySimpleStateIf(attributes_map_float, isNotNull(call_parts.started_at)) as attributes_map_float,
        anySimpleStateIf(attributes_map_bool, isNotNull(call_parts.started_at)) as attributes_map_bool,
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

-- Step 4: Add typed maps to calls_complete.
ALTER TABLE calls_complete
    ADD COLUMN attributes_map_str   Map(String, String),
    ADD COLUMN attributes_map_int   Map(String, Int64),
    ADD COLUMN attributes_map_float Map(String, Float64),
    ADD COLUMN attributes_map_bool  Map(String, Bool);
