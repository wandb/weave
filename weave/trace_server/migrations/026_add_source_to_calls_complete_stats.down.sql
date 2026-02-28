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
    minSimpleState(calls_complete.created_at) as created_at,
    maxSimpleState(calls_complete.updated_at) as updated_at,
    argMaxState(calls_complete.display_name, calls_complete.created_at) as display_name
FROM calls_complete
GROUP BY
    calls_complete.project_id,
    calls_complete.id;

ALTER TABLE calls_complete_stats DROP COLUMN source;
