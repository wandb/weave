CREATE TABLE calls_raw (
    project_id String,
    id String,
    # Start Fields (All fields except parent_id are required when starting
    # a call. However, to support a fast "update" we need to allow nulls)
    trace_id String NULL,
    parent_id String NULL,
    # This field is actually nullable
    name String NULL,
    start_datetime DateTime64(3) NULL,
    attributes_dump String NULL,
    inputs_dump String NULL,
    input_refs Array(String),
    # Empty array treated as null
    # End Fields (All fields are required when ending
    # a call. However, to support a fast "update" we need to allow nulls)
    end_datetime DateTime64(3) NULL,
    outputs_dump String NULL,
    summary_dump String NULL,
    exception String NULL,
    output_refs Array(String),
    # Empty array treated as null
    # Bookkeeping
    db_row_created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree
ORDER BY (project_id, id);
CREATE TABLE calls_merged (
    project_id String,
    id String,
    # While these fields are all marked as null, the practical expectation
    # is that they will be non-null except for parent_id. The problem is that
    # clickhouse might not aggregate the data immediately, so we need to allow
    # for nulls in the interim.
    trace_id SimpleAggregateFunction(any, Nullable(String)),
    parent_id SimpleAggregateFunction(any, Nullable(String)),
    name SimpleAggregateFunction(any, Nullable(String)),
    start_datetime SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    attributes_dump SimpleAggregateFunction(any, Nullable(String)),
    inputs_dump SimpleAggregateFunction(any, Nullable(String)),
    input_refs SimpleAggregateFunction(array_concat_agg, Array(String)),
    end_datetime SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    outputs_dump SimpleAggregateFunction(any, Nullable(String)),
    summary_dump SimpleAggregateFunction(any, Nullable(String)),
    exception SimpleAggregateFunction(any, Nullable(String)),
    output_refs SimpleAggregateFunction(array_concat_agg, Array(String))
) ENGINE = AggregatingMergeTree
ORDER BY (project_id, id);
CREATE MATERIALIZED VIEW calls_merged_view TO calls_merged AS
SELECT project_id,
    id,
    anySimpleState(trace_id) as trace_id,
    anySimpleState(parent_id) as parent_id,
    anySimpleState(name) as name,
    anySimpleState(start_datetime) as start_datetime,
    anySimpleState(attributes_dump) as attributes_dump,
    anySimpleState(inputs_dump) as inputs_dump,
    array_concat_aggSimpleState(input_refs) as input_refs,
    anySimpleState(end_datetime) as end_datetime,
    anySimpleState(outputs_dump) as outputs_dump,
    anySimpleState(summary_dump) as summary_dump,
    anySimpleState(exception) as exception,
    array_concat_aggSimpleState(output_refs) as output_refs
FROM calls_raw
GROUP BY project_id,
    id
