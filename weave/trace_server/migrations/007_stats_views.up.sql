CREATE TABLE files_stats
(
    project_id String,
    digest String,
    chunk_index UInt32,
    n_chunks SimpleAggregateFunction(any, UInt32),
    name SimpleAggregateFunction(any, String),
    size_bytes SimpleAggregateFunction(any, UInt64),
    created_at SimpleAggregateFunction(min, DateTime64(3)),
    updated_at SimpleAggregateFunction(max, DateTime64(3))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, digest, chunk_index);

CREATE MATERIALIZED VIEW files_stats_view
TO weave_trace_db.files_stats
AS
SELECT
    project_id,
    digest,
    chunk_index,
    anySimpleState(n_chunks) as n_chunks,
    anySimpleState(name) as name,
    anySimpleState(length(val_bytes)) AS size_bytes,
    minSimpleState(created_at) AS created_at,
    maxSimpleState(created_at) AS updated_at
FROM weave_trace_db.files
GROUP BY
    project_id,
    digest,
    chunk_index;

CREATE TABLE table_rows_stats
(
    project_id String,
    digest String,
    refs SimpleAggregateFunction(any, Array(String)),
    size_bytes SimpleAggregateFunction(any, UInt64),
    created_at SimpleAggregateFunction(min, DateTime64(3)),
    updated_at SimpleAggregateFunction(max, DateTime64(3))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, digest);

CREATE MATERIALIZED VIEW table_rows_stats_view
TO weave_trace_db.table_rows_stats
AS
SELECT
    project_id,
    digest,
    anySimpleState(refs) as refs,
    anySimpleState(length(val_dump)) AS size_bytes,
    minSimpleState(created_at) AS created_at,
    maxSimpleState(created_at) AS updated_at
FROM weave_trace_db.table_rows
GROUP BY
    project_id, digest;


CREATE TABLE object_versions_stats
(
    project_id String,
    kind Enum('op', 'object'),
    object_id String,
    digest String,
    base_object_class SimpleAggregateFunction(any, Nullable(String)),
    refs SimpleAggregateFunction(any, Array(String)),
    size_bytes SimpleAggregateFunction(any, UInt64),
    created_at SimpleAggregateFunction(min, DateTime64(3)),
    updated_at SimpleAggregateFunction(max, DateTime64(3))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, kind, object_id, digest);

CREATE MATERIALIZED VIEW object_versions_stats_view
TO weave_trace_db.object_versions_stats
AS
SELECT
    project_id,
    kind,
    object_id,
    digest,
    anySimpleState(base_object_class) AS base_object_class,
    anySimpleState(refs) AS refs,
    anySimpleState(length(val_dump)) AS size_bytes,
    minSimpleState(created_at) AS created_at,
    maxSimpleState(created_at) AS updated_at
FROM weave_trace_db.object_versions
GROUP BY
    project_id, kind, object_id, digest;

CREATE TABLE calls_merged_stats
(
    project_id String,
    id String,
    trace_id SimpleAggregateFunction(any, Nullable(String)),
    parent_id SimpleAggregateFunction(any, Nullable(String)),
    op_name SimpleAggregateFunction(any, Nullable(String)),
    started_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    attributes_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    inputs_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    input_refs SimpleAggregateFunction(groupArrayArray, Array(String)),
    ended_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    output_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    summary_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    exception SimpleAggregateFunction(any, Nullable(String)),
    output_refs SimpleAggregateFunction(groupArrayArray, Array(String)),
    wb_user_id SimpleAggregateFunction(any, Nullable(String)),
    wb_run_id SimpleAggregateFunction(any, Nullable(String)),
    updated_at SimpleAggregateFunction(max, DateTime64(3)),
    deleted_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    display_name AggregateFunction(argMax, Nullable(String), DateTime64(3))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, id);

-- NOTE: This needs to be generally kept in sync with calls_merged.
CREATE MATERIALIZED VIEW calls_merged_stats_view
TO weave_trace_db.calls_merged_stats
AS
SELECT
    project_id,
    id,
    anySimpleState(trace_id) as trace_id,
    anySimpleState(parent_id) as parent_id,
    anySimpleState(op_name) as op_name,
    anySimpleState(started_at) as started_at,
    anySimpleState(length(attributes_dump)) as attributes_size_bytes,
    anySimpleState(length(inputs_dump)) as inputs_size_bytes,
    anySimpleState(input_refs) as input_refs,
    anySimpleState(ended_at) as ended_at,
    anySimpleState(length(output_dump)) as output_size_bytes,
    anySimpleState(length(summary_dump)) as summary_size_bytes,
    anySimpleState(exception) as exception,
    anySimpleState(output_refs) as output_refs,
    anySimpleState(wb_user_id) as wb_user_id,
    anySimpleState(wb_run_id) as wb_run_id,
    anySimpleState(deleted_at) as deleted_at,
    maxSimpleState(created_at) as updated_at,
    argMaxSimpleState(display_name, created_at) as display_name
FROM weave_trace_db.call_parts
GROUP BY project_id, id;
