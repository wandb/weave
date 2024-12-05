/*
`call_parts` contains the raw data for each call. In particular, for each
logical "call" will contain 2 rows: one for the start and one for the end. Note:
it is possible that a single `call_parts` row will contain both the start and
end data, but this is not practically possible given the current APIs. The
`calls_merged` table is a materialized view that aggregates the start and end
data into a single row.
*/
CREATE TABLE call_parts (
    /*
    `id`: The unique identifier for the call. This is typically a UUID.
    */
    id String,
    /*
    `project_id`: The project identifier for the call. In practice, this is an internal
    identifier that matches the project identifier in the W&B API.
    */
    project_id String,
    /*
    `parent_id`: The ID of the parent call. This is typically a UUID.
        - Required for call-start (if the call is not a top-level root call)
    */
    parent_id String NULL,
    /*
    `trace_id`: The ID of the trace that this call is part of. This is typically a UUID.
        - Required for call-start
    */
    trace_id String NULL,
    /*
    `op_name`: The name of the operation that was called. This is most often a ref string
    referring to the Op that produced the call. However, it can also be a string
        - Required for call-start
    */
    op_name String NULL,
    /*
    `started_at`: The time that the call started. No timezone information is stored and the
    precision is to the millisecond.
       - Required for call-start
    */
    started_at DateTime64(3) NULL,
    /*
    `attributes_dump`: A `json.dumps` of the attributes of the call. Attributes are essentially
    metadata about the call itself and are not the inputs or outputs of the call.
       - Required for call-start
    */
    attributes_dump String NULL,
    /*
    `inputs_dump`: A `json.dumps` of the inputs to the call. This is typically a dictionary
    of the inputs to the call.
       - Required for call-start
    */
    inputs_dump String NULL,
    /*
    `input_refs`: A derived field that contains the references used in the inputs. This is
    used to track the dependencies of the call.
       - Required for call-start
    */
    input_refs Array(String),
    /*
    `ended_at`: The time that the call ended. No timezone information is stored and the
    precision is to the millisecond.
       - Required for call-end
    */
    ended_at DateTime64(3) NULL,
    /*
    `output_dump`: A `json.dumps` of the output of the call. This is not guaranteed to be
    a dictionary.
       - Required for call-end
    */
    output_dump String NULL,
    /*
    `summary_dump`: A `json.dumps` of the summary of the call. This is typically a dictionary
    of the summary of the call. Importantly, this is not the same as the output of the call. 
    In contrast to attributes, the summary is calculated after the call has completed.
       - Required for call-end
    */
    summary_dump String NULL,
    /*
    `exception`: A string representation of the exception that was raised during the call.
       - Required for call-end (if an exception was raised)
    */
    exception String NULL,
    /*
    `output_refs`: A derived field that contains the references used in the output. This is
    used to track the dependencies of the call.
       - Required for call-end
    */
    output_refs Array(String),
    /*
    `wb_user_id`: The ID of the user that created the call. This is the ID of the user in the
    W&B API.
    */
    wb_user_id Nullable(String),
    /*
    `wb_run_id`: The ID of the run that the call is part of. This is a composite of the 
    W&B Project ID and Run ID in the W&B API.
    */
    wb_run_id Nullable(String),
    /*
    `created_at`: The time that the row was inserted into the database.
    */
    created_at DateTime64(3) DEFAULT now64(3)
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
    op_name SimpleAggregateFunction(any, Nullable(String)),
    started_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    attributes_dump SimpleAggregateFunction(any, Nullable(String)),
    inputs_dump SimpleAggregateFunction(any, Nullable(String)),
    input_refs SimpleAggregateFunction(array_concat_agg, Array(String)),
    ended_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    output_dump SimpleAggregateFunction(any, Nullable(String)),
    summary_dump SimpleAggregateFunction(any, Nullable(String)),
    exception SimpleAggregateFunction(any, Nullable(String)),
    output_refs SimpleAggregateFunction(array_concat_agg, Array(String)),
    wb_user_id SimpleAggregateFunction(any, Nullable(String)),
    wb_run_id SimpleAggregateFunction(any, Nullable(String))
) ENGINE = AggregatingMergeTree
ORDER BY (project_id, id);

CREATE MATERIALIZED VIEW calls_merged_view TO calls_merged AS
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
    id;

CREATE TABLE object_versions (
    project_id String,
    object_id String,
    kind Enum('op', 'object'),
    base_object_class String NULL,
    refs Array(String),
    val_dump String,
    digest String,
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, kind, object_id, digest);

CREATE VIEW object_versions_deduped AS
SELECT project_id,
    object_id,
    created_at,
    kind,
    base_object_class,
    refs,
    val_dump,
    digest,
    if (kind = 'op', 1, 0) AS is_op,
    row_number() OVER (
        PARTITION BY project_id,
        kind,
        object_id
        ORDER BY created_at ASC
    ) AS _version_index_plus_1,
    _version_index_plus_1 - 1 AS version_index,
    count(*) OVER (PARTITION BY project_id, kind, object_id) as version_count,
    if(_version_index_plus_1 = version_count, 1, 0) AS is_latest
FROM (
        SELECT *,
            row_number() OVER (
                PARTITION BY project_id,
                kind,
                object_id,
                digest
                ORDER BY created_at ASC
            ) AS rn
        FROM object_versions
    )
WHERE rn = 1 WINDOW w AS (
        PARTITION BY project_id,
        kind,
        object_id
        ORDER BY created_at ASC
    )
ORDER BY project_id,
    kind,
    object_id,
    created_at;

CREATE TABLE table_rows (
    project_id String,
    digest String,
    refs Array(String),
    val_dump String,
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, digest);
CREATE VIEW table_rows_deduped AS
SELECT project_id, digest, val_dump
FROM (
        SELECT *,
            row_number() OVER (PARTITION BY project_id, digest) AS rn
        FROM table_rows
    )
WHERE rn = 1
ORDER BY project_id,
    digest;

CREATE TABLE tables (
    project_id String,
    digest String,
    row_digests Array(String),
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, digest);
CREATE VIEW tables_deduped AS
SELECT *
FROM (
        SELECT *,
            row_number() OVER (PARTITION BY project_id, digest) AS rn
        FROM tables
    )
WHERE rn = 1
ORDER BY project_id,
    digest;

CREATE TABLE files (
    project_id String,
    digest String,
    chunk_index UInt32,
    n_chunks UInt32,
    name String,
    val_bytes String,
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, digest, chunk_index);

CREATE VIEW files_deduped AS
SELECT *
FROM (
        SELECT *,
            row_number() OVER (PARTITION BY project_id, digest, chunk_index) AS rn
        FROM files
    )
WHERE rn = 1
ORDER BY project_id,
    digest,
    chunk_index;
