CREATE TABLE calls_merged_2 (
    project_id String,
    id String,
    trace_id SimpleAggregateFunction(any, Nullable(String)),
    parent_id SimpleAggregateFunction(any, Nullable(String)),
    op_name SimpleAggregateFunction(any, Nullable(String)),
    started_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    deleted_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    attributes_dump SimpleAggregateFunction(any, Nullable(String)),
    inputs_dump SimpleAggregateFunction(any, Nullable(String)),
    input_refs SimpleAggregateFunction(array_concat_agg, Array(String)),
    ended_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    output_dump SimpleAggregateFunction(any, Nullable(String)),
    summary_dump SimpleAggregateFunction(any, Nullable(String)),
    exception SimpleAggregateFunction(any, Nullable(String)),
    output_refs SimpleAggregateFunction(array_concat_agg, Array(String)),
    wb_user_id SimpleAggregateFunction(any, Nullable(String)),
    wb_run_id SimpleAggregateFunction(any, Nullable(String)),
    display_name AggregateFunction(argMax, Nullable(String), DateTime64(3))
) ENGINE = AggregatingMergeTree
ORDER BY (project_id, id, started_at);
SETTINGS min_bytes_for_wide_part = 0;

CREATE MATERIALIZED VIEW calls_merged_view_2 TO calls_merged_2 AS
SELECT project_id,
    id,
    anySimpleState(wb_run_id) as wb_run_id,
    anySimpleState(wb_user_id) as wb_user_id,
    anySimpleState(trace_id) as trace_id,
    anySimpleState(parent_id) as parent_id,
    anySimpleState(op_name) as op_name,
    anySimpleState(started_at) as started_at,
    anySimpleState(deleted_at) as deleted_at,
    argMaxState(display_name, call_parts.created_at) as display_name
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
    id;
ORDER BY project_id, id, started_at;