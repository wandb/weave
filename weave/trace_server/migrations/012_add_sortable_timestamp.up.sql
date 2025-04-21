-- Create non-nullable Datetime field in the call_merged table
ALTER TABLE calls_merged 
    ADD COLUMN sortable_datetime Datetime(6) DEFAULT coalesce(started_at, ended_at, NOW());

-- Add the column to the materialized view 
ALTER TABLE calls_merged_view MODIFY QUERY
    SELECT project_id,
        id,
        anySimpleState(wb_run_id) as wb_run_id,
        anySimpleStateIf(wb_user_id, isNotNull(call_parts.started_at)) as wb_user_id,
        anySimpleState(trace_id) as trace_id,
        anySimpleState(parent_id) as parent_id,
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
        anySimpleState(coalesce(call_parts.started_at, call_parts.ended_at, call_parts.created_at)) as sortable_datetime
    FROM call_parts
    GROUP BY project_id,
        id;
-- Matialize the column
ALTER TABLE calls_merged MATERIALIZE COLUMN sortable_datetime;

-- Add minmax index  on the new column
ALTER TABLE calls_merged ADD INDEX idx_sortable_datetime (sortable_datetime) TYPE minmax GRANULARITY 1;
-- Materialize the index, actually generating index marks for all the granules
ALTER TABLE calls_merged MATERIALIZE INDEX idx_sortable_datetime;
