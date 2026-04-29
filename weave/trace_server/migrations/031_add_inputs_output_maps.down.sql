-- Migration 031 down: drop typed inputs/output maps and revert
-- calls_merged_view to migration 029's shape.

-- Step 1: Restore calls_merged_view to the pre-031 query (matches the
-- final form set by migration 029). Must run before dropping columns so
-- the view stops referencing them.
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

-- Step 2: Drop typed maps from calls_complete.
ALTER TABLE calls_complete
    DROP COLUMN IF EXISTS inputs_map_str,
    DROP COLUMN IF EXISTS inputs_map_int,
    DROP COLUMN IF EXISTS inputs_map_float,
    DROP COLUMN IF EXISTS inputs_map_bool,
    DROP COLUMN IF EXISTS output_map_str,
    DROP COLUMN IF EXISTS output_map_int,
    DROP COLUMN IF EXISTS output_map_float,
    DROP COLUMN IF EXISTS output_map_bool;

-- Step 3: Drop typed maps from calls_merged.
ALTER TABLE calls_merged
    DROP COLUMN IF EXISTS inputs_map_str,
    DROP COLUMN IF EXISTS inputs_map_int,
    DROP COLUMN IF EXISTS inputs_map_float,
    DROP COLUMN IF EXISTS inputs_map_bool,
    DROP COLUMN IF EXISTS output_map_str,
    DROP COLUMN IF EXISTS output_map_int,
    DROP COLUMN IF EXISTS output_map_float,
    DROP COLUMN IF EXISTS output_map_bool;

-- Step 4: Drop typed maps from call_parts.
ALTER TABLE call_parts
    DROP COLUMN IF EXISTS inputs_map_str,
    DROP COLUMN IF EXISTS inputs_map_int,
    DROP COLUMN IF EXISTS inputs_map_float,
    DROP COLUMN IF EXISTS inputs_map_bool,
    DROP COLUMN IF EXISTS output_map_str,
    DROP COLUMN IF EXISTS output_map_int,
    DROP COLUMN IF EXISTS output_map_float,
    DROP COLUMN IF EXISTS output_map_bool;
