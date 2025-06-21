-- Add thread_id to raw call parts table
ALTER TABLE call_parts
    ADD COLUMN thread_id Nullable(String) DEFAULT NULL;

-- Add thread_id to aggregated calls table
ALTER TABLE calls_merged
    ADD COLUMN thread_id SimpleAggregateFunction(any, Nullable(String));

-- Update materialized view to include thread_id
ALTER TABLE calls_merged_view MODIFY QUERY
    SELECT project_id,
        id,
        anySimpleState(wb_run_id) as wb_run_id,
        anySimpleState(wb_run_step) as wb_run_step,
        anySimpleStateIf(wb_user_id, isNotNull(call_parts.started_at)) as wb_user_id,
        anySimpleState(trace_id) as trace_id,
        anySimpleState(parent_id) as parent_id,
        anySimpleState(thread_id) as thread_id,
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

 