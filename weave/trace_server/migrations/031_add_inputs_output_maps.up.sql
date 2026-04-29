-- Migration 031: Add typed inputs/output maps for fast filtering.
--
-- Adds eight Map columns alongside inputs_dump / output_dump on call_parts,
-- calls_merged, and calls_complete. The typed maps are populated at ingest
-- by walking the inputs / output payload, dot-flattening dict paths, and
-- routing each scalar leaf into the map matching its Python type. Read-path
-- filters with a known type (via $convert) hit the typed map directly
-- instead of JSON_VALUE over inputs_dump / output_dump.
--
-- inputs_dump / output_dump are preserved (typed maps are a duplicated
-- read-path index). Existing rows get empty maps by default and continue
-- to work via the JSON_VALUE fallback. Per-row entry caps and a string
-- length cap keep map cardinality bounded — see extract_typed_payload.

-- Step 1: Add typed maps to call_parts. Map columns default to empty map
-- in ClickHouse, so no explicit DEFAULT clause is needed.
ALTER TABLE call_parts
    ADD COLUMN inputs_map_str    Map(String, String),
    ADD COLUMN inputs_map_int    Map(String, Int64),
    ADD COLUMN inputs_map_float  Map(String, Float64),
    ADD COLUMN inputs_map_bool   Map(String, Bool),
    ADD COLUMN output_map_str    Map(String, String),
    ADD COLUMN output_map_int    Map(String, Int64),
    ADD COLUMN output_map_float  Map(String, Float64),
    ADD COLUMN output_map_bool   Map(String, Bool);

-- Step 2: Add typed maps to calls_merged as SimpleAggregateFunction(any, ...)
-- to match the existing AMT aggregation pattern.
ALTER TABLE calls_merged
    ADD COLUMN inputs_map_str    SimpleAggregateFunction(any, Map(String, String)),
    ADD COLUMN inputs_map_int    SimpleAggregateFunction(any, Map(String, Int64)),
    ADD COLUMN inputs_map_float  SimpleAggregateFunction(any, Map(String, Float64)),
    ADD COLUMN inputs_map_bool   SimpleAggregateFunction(any, Map(String, Bool)),
    ADD COLUMN output_map_str    SimpleAggregateFunction(any, Map(String, String)),
    ADD COLUMN output_map_int    SimpleAggregateFunction(any, Map(String, Int64)),
    ADD COLUMN output_map_float  SimpleAggregateFunction(any, Map(String, Float64)),
    ADD COLUMN output_map_bool   SimpleAggregateFunction(any, Map(String, Bool));

-- Step 3: Propagate typed maps through calls_merged_view. inputs maps come
-- from start rows (gated on isNotNull(started_at)) and output maps come
-- from end rows (gated on isNotNull(ended_at)), so empty defaults from
-- the "other" half can't win under SimpleAggregateFunction(any).
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
        anySimpleStateIf(inputs_map_str, isNotNull(call_parts.started_at)) as inputs_map_str,
        anySimpleStateIf(inputs_map_int, isNotNull(call_parts.started_at)) as inputs_map_int,
        anySimpleStateIf(inputs_map_float, isNotNull(call_parts.started_at)) as inputs_map_float,
        anySimpleStateIf(inputs_map_bool, isNotNull(call_parts.started_at)) as inputs_map_bool,
        array_concat_aggSimpleState(input_refs) as input_refs,
        anySimpleState(ended_at) as ended_at,
        anySimpleState(output_dump) as output_dump,
        anySimpleStateIf(output_map_str, isNotNull(call_parts.ended_at)) as output_map_str,
        anySimpleStateIf(output_map_int, isNotNull(call_parts.ended_at)) as output_map_int,
        anySimpleStateIf(output_map_float, isNotNull(call_parts.ended_at)) as output_map_float,
        anySimpleStateIf(output_map_bool, isNotNull(call_parts.ended_at)) as output_map_bool,
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
    ADD COLUMN inputs_map_str    Map(String, String),
    ADD COLUMN inputs_map_int    Map(String, Int64),
    ADD COLUMN inputs_map_float  Map(String, Float64),
    ADD COLUMN inputs_map_bool   Map(String, Bool),
    ADD COLUMN output_map_str    Map(String, String),
    ADD COLUMN output_map_int    Map(String, Int64),
    ADD COLUMN output_map_float  Map(String, Float64),
    ADD COLUMN output_map_bool   Map(String, Bool);
