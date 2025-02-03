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
TO files_stats
AS
SELECT
    files.project_id,
    files.digest,
    files.chunk_index,
    anySimpleState(files.n_chunks) as n_chunks,
    anySimpleState(files.name) as name,
    anySimpleState(length(files.val_bytes)) AS size_bytes,
    minSimpleState(files.created_at) AS created_at,
    maxSimpleState(files.created_at) AS updated_at
FROM files
GROUP BY
    files.project_id,
    files.digest,
    files.chunk_index;

CREATE TABLE table_rows_stats
(
    project_id String,
    digest String,
    size_bytes SimpleAggregateFunction(any, UInt64),
    created_at SimpleAggregateFunction(min, DateTime64(3)),
    updated_at SimpleAggregateFunction(max, DateTime64(3))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, digest);

CREATE MATERIALIZED VIEW table_rows_stats_view
TO table_rows_stats
AS
SELECT
    table_rows.project_id,
    table_rows.digest,
    anySimpleState(length(table_rows.val_dump)) AS size_bytes,
    minSimpleState(table_rows.created_at) AS created_at,
    maxSimpleState(table_rows.created_at) AS updated_at
FROM table_rows
GROUP BY
    table_rows.project_id,
    table_rows.digest;


CREATE TABLE object_versions_stats
(
    project_id String,
    kind Enum('op', 'object'),
    object_id String,
    digest String,
    base_object_class SimpleAggregateFunction(any, Nullable(String)),
    size_bytes SimpleAggregateFunction(any, UInt64),
    created_at SimpleAggregateFunction(min, DateTime64(3)),
    updated_at SimpleAggregateFunction(max, DateTime64(3))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, kind, object_id, digest);

CREATE MATERIALIZED VIEW object_versions_stats_view
TO object_versions_stats
AS
SELECT
    object_versions.project_id,
    object_versions.kind,
    object_versions.object_id,
    object_versions.digest,
    anySimpleState(object_versions.base_object_class) AS base_object_class,
    anySimpleState(length(object_versions.val_dump)) AS size_bytes,
    minSimpleState(object_versions.created_at) AS created_at,
    maxSimpleState(object_versions.created_at) AS updated_at
FROM object_versions
GROUP BY
    object_versions.project_id,
    object_versions.kind,
    object_versions.object_id,
    object_versions.digest;

CREATE TABLE feedback_stats
(
    project_id String,
    weave_ref String,
    wb_user_id String,
    id String,
    creator SimpleAggregateFunction(any, Nullable(String)),
    created_at SimpleAggregateFunction(min, DateTime64(3)),
    updated_at SimpleAggregateFunction(max, DateTime64(3)),
    feedback_type SimpleAggregateFunction(any, String),
    payload_size_bytes SimpleAggregateFunction(any, UInt64),
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, weave_ref, wb_user_id, id);

CREATE MATERIALIZED VIEW feedback_stats_view
TO feedback_stats
AS
SELECT
    feedback.project_id,
    feedback.weave_ref,
    feedback.wb_user_id,
    feedback.id,
    anySimpleState(feedback.creator) as creator,
    minSimpleState(feedback.created_at) as created_at,
    maxSimpleState(feedback.created_at) as updated_at,
    argMaxState(feedback.feedback_type, feedback.created_at) as feedback_type,
    anySimpleState(length(feedback.payload_dump)) as payload_size_bytes
FROM feedback
GROUP BY
    feedback.project_id,
    feedback.weave_ref,
    feedback.wb_user_id,
    feedback.id;

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
    ended_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    output_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    summary_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    exception_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    wb_user_id SimpleAggregateFunction(any, Nullable(String)),
    wb_run_id SimpleAggregateFunction(any, Nullable(String)),
    updated_at SimpleAggregateFunction(max, DateTime64(3)),
    deleted_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    display_name AggregateFunction(argMax, Nullable(String), DateTime64(3))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, id);

-- NOTE: This needs to be generally kept in sync with calls_merged.
CREATE MATERIALIZED VIEW calls_merged_stats_view
TO calls_merged_stats
AS
SELECT
    call_parts.project_id,
    call_parts.id,
    anySimpleState(call_parts.trace_id) as trace_id,
    anySimpleState(call_parts.parent_id) as parent_id,
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
    anySimpleState(call_parts.deleted_at) as deleted_at,
    maxSimpleState(call_parts.created_at) as updated_at,
    argMaxState(call_parts.display_name, call_parts.created_at) as display_name
FROM call_parts
GROUP BY
    call_parts.project_id,
    call_parts.id;
