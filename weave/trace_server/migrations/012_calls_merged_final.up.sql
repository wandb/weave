
CREATE TABLE IF NOT EXISTS calls_merged_final (
    id String,
    project_id String,
    started_at DateTime64(6),

    trace_id SimpleAggregateFunction(any, String),
    op_name SimpleAggregateFunction(any, String),
    parent_id SimpleAggregateFunction(any, Nullable(String)),
    ended_at SimpleAggregateFunction(any, Nullable(DateTime64(6))),

    deleted_at SimpleAggregateFunction(any, Nullable(DateTime64(6))),
    display_name SimpleAggregateFunction(any, Nullable(String)),
    
    inputs_dump SimpleAggregateFunction(any, String),
    attributes_dump SimpleAggregateFunction(any, String),
    output_dump SimpleAggregateFunction(any, Nullable(String)),
    summary_dump SimpleAggregateFunction(any, Nullable(String)),

    input_refs SimpleAggregateFunction(array_concat_agg, Array(String)),
    output_refs SimpleAggregateFunction(array_concat_agg, Array(String)),
    
    exception SimpleAggregateFunction(any, Nullable(String)),
    wb_run_id SimpleAggregateFunction(any, Nullable(String)),
    wb_user_id SimpleAggregateFunction(any, String),

    -- Computed fields?
    -- duration_ms Float64,
    -- status String,
    -- trace_name String,
    -- cost_total Float64,
    -- storage_size_bytes UInt64,
    -- storage_size_bytes_total UInt64,
    -- storage_size_bytes_total_raw UInt64,

    INDEX idx_op_name op_name TYPE bloom_filter(0.01) GRANULARITY 1,
    -- More indices? trace_id? do we want to go crazy and try to index inputs/output?
    
) ENGINE = AggregatingMergeTree
ORDER BY (project_id, started_at);

CREATE MATERIALIZED VIEW calls_merged_final_view TO calls_merged_final AS
SELECT
    id,
    project_id,
    anySimpleState(calls_merged.started_at) as started_at,

    anySimpleState(wb_run_id) as wb_run_id,
    anySimpleStateIf(wb_user_id, isNotNull(calls_merged.started_at)) as wb_user_id,
    anySimpleState(trace_id) as trace_id,
    anySimpleState(parent_id) as parent_id,
    anySimpleState(op_name) as op_name,
    anySimpleState(ended_at) as ended_at,
    anySimpleState(attributes_dump) as attributes_dump,
    anySimpleState(inputs_dump) as inputs_dump,
    anySimpleState(output_dump) as output_dump,
    array_concat_aggSimpleState(input_refs) as input_refs,
    array_concat_aggSimpleState(output_refs) as output_refs,
    anySimpleState(exception) as exception,
    anySimpleState(deleted_at) as deleted_at,
    anySimpleState(summary_dump) as summary_dump,
    anySimpleState(display_name) as display_name
FROM calls_merged
WHERE isNotNull(calls_merged.started_at)
GROUP BY
    project_id,
    id;
