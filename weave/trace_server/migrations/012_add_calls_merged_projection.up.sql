CREATE MATERIALIZED VIEW calls_merged_view_ordered TO calls_merged AS
SELECT project_id,
    id,
    anySimpleState(wb_run_id) as wb_run_id,
    anySimpleState(wb_user_id) as wb_user_id,
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
    array_concat_aggSimpleState(output_refs) as output_refs
FROM call_parts
GROUP BY project_id,
    id
ORDER BY (project_id, started_at)
