-- Drop errantly added DUMP from stats table
ALTER TABLE calls_merged_stats DROP COLUMN otel_dump;
 
-- Add otel_dump_size_bytes (NOT DUMP) to stats table
ALTER TABLE calls_merged_stats
    ADD COLUMN otel_dump_size_bytes SimpleAggregateFunction(any, Nullable(UInt64));

-- Update stats materialized view with the bytes field
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
    anySimpleState(length(call_parts.otel_dump)) as otel_dump_size_bytes
FROM call_parts
GROUP BY
    call_parts.project_id,
    call_parts.id;
