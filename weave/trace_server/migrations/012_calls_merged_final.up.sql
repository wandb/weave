
CREATE TABLE IF NOT EXISTS calls_merged_final (
    id String,
    project_id String,
    started_at DateTime64(6),
    inv_started_at DateTime64(6),

    trace_id SimpleAggregateFunction(any, String),
    op_name SimpleAggregateFunction(any, String),
    parent_id SimpleAggregateFunction(any, Nullable(String)),
    ended_at SimpleAggregateFunction(any, Nullable(DateTime64(6))),

    deleted_at SimpleAggregateFunction(any, Nullable(DateTime64(6))),
    display_name SimpleAggregateFunction(any, Nullable(String)),

    inputs_dump SimpleAggregateFunction(any, String),
    attributes_dump SimpleAggregateFunction(any, String),
    output_dump SimpleAggregateFunction(any, String),
    summary_dump SimpleAggregateFunction(any, String),

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

    INDEX idx_op_name op_name TYPE bloom_filter,
    INDEX idx_trace_id trace_id TYPE minmax,
    INDEX idx_parent_id parent_id TYPE minmax,
    
    INDEX idx_inputs_dump inputs_dump TYPE bloom_filter,
    INDEX idx_output_dump output_dump TYPE bloom_filter,

) ENGINE = AggregatingMergeTree
ORDER BY (project_id, inv_started_at);

CREATE TABLE IF NOT EXISTS temp(
    id String,
    project_id String,
    started_at DateTime64(6),
    created_at DateTime64(6),
    inv_started_at DateTime64(6),
    wb_run_id String,
    wb_user_id String,
    trace_id String,
    parent_id String,
    op_name String,
    ended_at DateTime64(6),
    attributes_dump String,
    inputs_dump String,
    output_dump String,
    summary_dump String,
    display_name String,
    input_refs Array(String) DEFAULT [],
    output_refs Array(String) DEFAULT [],
    exception String,
    deleted_at DateTime64(6),
) ENGINE=Null;

CREATE MATERIALIZED VIEW IF NOT EXISTS calls_merged_final_view TO calls_merged_final AS
SELECT
    id,
    project_id,
    anySimpleState(coalesce(temp.started_at, temp.created_at)) as started_at,
    anySimpleState(-toUnixTimestamp(coalesce(temp.started_at, temp.created_at))) AS inv_started_at,

    anySimpleState(wb_run_id) as wb_run_id,
    anySimpleStateIf(wb_user_id, isNotNull(temp.started_at)) as wb_user_id,
    anySimpleState(trace_id) as trace_id,
    anySimpleState(parent_id) as parent_id,
    anySimpleState(op_name) as op_name,
    anySimpleState(ended_at) as ended_at,
    anySimpleState(attributes_dump) as attributes_dump,
    anySimpleState(inputs_dump) as inputs_dump,
    anySimpleState(coalesce(output_dump, '{}')) as output_dump,
    array_concat_aggSimpleState(input_refs) as input_refs,
    array_concat_aggSimpleState(output_refs) as output_refs,
    anySimpleState(exception) as exception,
    anySimpleState(deleted_at) as deleted_at,
    anySimpleState(coalesce(summary_dump, '{}')) as summary_dump,
    anySimpleState(display_name) as display_name
FROM temp
GROUP BY
    project_id,
    id;

INSERT INTO temp SELECT *, -toUnixTimestamp(coalesce(started_at, created_at)) AS inv_started_at FROM call_parts;
drop table calls_merged_final_view;
drop table temp;

CREATE MATERIALIZED VIEW IF NOT EXISTS calls_merged_final_view TO calls_merged_final AS
SELECT
    id,
    project_id,
    anySimpleState(coalesce(call_parts.started_at, call_parts.created_at)) as started_at,
    anySimpleState(-toUnixTimestamp(coalesce(call_parts.started_at, call_parts.created_at))) AS inv_started_at,

    anySimpleState(wb_run_id) as wb_run_id,
    anySimpleStateIf(wb_user_id, isNotNull(call_parts.started_at)) as wb_user_id,
    anySimpleState(trace_id) as trace_id,
    anySimpleState(parent_id) as parent_id,
    anySimpleState(op_name) as op_name,
    anySimpleState(ended_at) as ended_at,
    anySimpleState(attributes_dump) as attributes_dump,
    anySimpleState(inputs_dump) as inputs_dump,
    anySimpleState(coalesce(output_dump, '{}')) as output_dump,
    array_concat_aggSimpleState(input_refs) as input_refs,
    array_concat_aggSimpleState(output_refs) as output_refs,
    anySimpleState(exception) as exception,
    anySimpleState(deleted_at) as deleted_at,
    anySimpleState(coalesce(summary_dump, '{}')) as summary_dump,
    anySimpleState(display_name) as display_name
FROM call_parts
GROUP BY
    project_id,
    id;


-- IDEA: https://gist.github.com/den-crane/f7382cd4f1f859ff6ac46afe7dc9925a