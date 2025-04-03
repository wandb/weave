
CREATE TABLE calls_merged_final (
    id String,
    project_id String,
    started_at DateTime64(6),

    parent_id SimpleAggregateFunction(any, Nullable(String)),
    trace_id SimpleAggregateFunction(any, String),
    op_name SimpleAggregateFunction(any, String),
    ended_at SimpleAggregateFunction(any, Nullable(DateTime64(6))),

    deleted_at SimpleAggregateFunction(any, Nullable(DateTime64(6))),
    display_name SimpleAggregateFunction(any, Nullable(String)),
    
    summary_dump SimpleAggregateFunction(any, String),
    attributes_dump SimpleAggregateFunction(any, String),
    inputs_dump SimpleAggregateFunction(any, String),
    output_dump SimpleAggregateFunction(any, String),

    input_refs SimpleAggregateFunction(array_concat_agg, Array(String)),
    output_refs SimpleAggregateFunction(array_concat_agg, Array(String)),
    
    exception SimpleAggregateFunction(any, Nullable(String)),
    wb_run_id SimpleAggregateFunction(any, Nullable(String)),
    wb_user_id SimpleAggregateFunction(any, String)

    -- Computed fields?
    -- duration_ms Float64,
    -- status String,
    -- trace_name String,
    -- cost_total Float64,
    -- storage_size_bytes UInt64,
    -- storage_size_bytes_total UInt64,
    -- storage_size_bytes_total_raw UInt64,
    
) ENGINE = AggregatingMergeTree
ORDER BY (project_id, started_at);

CREATE MATERIALIZED VIEW calls_merged_final_view TO calls_merged_final AS
SELECT
    id,
    project_id,
    calls_merged.started_at as started_at,

    anySimpleMergeState(wb_run_id) as wb_run_id,
    anySimpleMergeStateIf(wb_user_id, isNotNull(call_parts.started_at)) as wb_user_id,
    anySimpleMergeState(trace_id) as trace_id,
    anySimpleMergeState(parent_id) as parent_id,
    anySimpleMergeState(op_name) as op_name,
    anySimpleMergeState(ended_at) as ended_at,
    anySimpleMergeState(attributes_dump) as attributes_dump,
    anySimpleMergeState(inputs_dump) as inputs_dump,
    anySimpleMergeState(output_dump) as output_dump,
    array_concat_aggSimpleMergeState(input_refs) as input_refs,
    array_concat_aggSimpleMergeState(output_refs) as output_refs,
    anySimpleMergeState(exception) as exception,
    anySimpleMergeState(deleted_at) as deleted_at,
    anySimpleMergeState(summary_dump) as summary_dump,
    argMaxMergeState(display_name, call_parts.created_at) as display_name
FROM calls_merged
-- do i need to push this into a having?
WHERE isNotNull(calls_merged.started_at)
GROUP BY
    project_id,
    id;
