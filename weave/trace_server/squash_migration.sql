-- ============================================================================
-- Squash migration: final schema state after all migrations through version 028
--
-- This file is used for fresh database installations as a performance
-- optimization. Instead of running all individual migrations sequentially,
-- we apply this single file to create the complete schema in one pass.
--
-- IMPORTANT: When adding a new migration (029+), you MUST also update this
-- file to reflect the new schema state. See migrations/README.md for details.
-- A CI test enforces that this file stays in sync with the sequential
-- migrations.
-- ============================================================================

-- ============================================================================
-- call_parts: Raw call data (start + end rows per logical call)
-- ============================================================================
CREATE TABLE call_parts (
    id String,
    project_id String,
    parent_id String NULL,
    trace_id String NULL,
    op_name String NULL,
    started_at Nullable(DateTime64(6)),
    attributes_dump String NULL,
    inputs_dump String NULL,
    input_refs Array(String),
    ended_at Nullable(DateTime64(6)),
    output_dump String NULL,
    summary_dump String NULL,
    exception String NULL,
    output_refs Array(String),
    wb_user_id Nullable(String),
    wb_run_id Nullable(String),
    created_at DateTime64(3) DEFAULT now64(3),
    deleted_at Nullable(DateTime64(3)) DEFAULT NULL,
    display_name Nullable(String) DEFAULT NULL,
    wb_run_step Nullable(UInt64) DEFAULT NULL,
    thread_id Nullable(String) DEFAULT NULL,
    turn_id Nullable(String) DEFAULT NULL,
    wb_run_step_end Nullable(UInt64) DEFAULT NULL,
    otel_dump Nullable(String)
) ENGINE = MergeTree
ORDER BY (project_id, id);

-- ============================================================================
-- calls_merged: Aggregated view of call_parts (start + end merged)
-- ============================================================================
CREATE TABLE calls_merged (
    project_id String,
    id String,
    trace_id SimpleAggregateFunction(any, Nullable(String)),
    parent_id SimpleAggregateFunction(any, Nullable(String)),
    op_name SimpleAggregateFunction(any, Nullable(String)),
    started_at SimpleAggregateFunction(any, Nullable(DateTime64(6))),
    attributes_dump SimpleAggregateFunction(any, Nullable(String)),
    inputs_dump SimpleAggregateFunction(any, Nullable(String)),
    input_refs SimpleAggregateFunction(array_concat_agg, Array(String)),
    ended_at SimpleAggregateFunction(any, Nullable(DateTime64(6))),
    output_dump SimpleAggregateFunction(any, Nullable(String)),
    summary_dump SimpleAggregateFunction(any, Nullable(String)),
    exception SimpleAggregateFunction(any, Nullable(String)),
    output_refs SimpleAggregateFunction(array_concat_agg, Array(String)),
    wb_user_id SimpleAggregateFunction(any, Nullable(String)),
    wb_run_id SimpleAggregateFunction(any, Nullable(String)),
    deleted_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    display_name AggregateFunction(argMax, Nullable(String), DateTime64(3)),
    sortable_datetime Datetime(6) DEFAULT coalesce(started_at, ended_at, NOW()),
    wb_run_step SimpleAggregateFunction(any, Nullable(UInt64)),
    thread_id SimpleAggregateFunction(any, Nullable(String)),
    turn_id SimpleAggregateFunction(any, Nullable(String)),
    wb_run_step_end SimpleAggregateFunction(any, Nullable(UInt64)),
    otel_dump SimpleAggregateFunction(any, Nullable(String)),
    INDEX idx_sortable_datetime (sortable_datetime) TYPE minmax GRANULARITY 1,
    INDEX idx_wb_run_id (wb_run_id) TYPE set(100) GRANULARITY 1
) ENGINE = AggregatingMergeTree
ORDER BY (project_id, id);

CREATE MATERIALIZED VIEW calls_merged_view TO calls_merged AS
SELECT project_id,
    id,
    anySimpleState(wb_run_id) as wb_run_id,
    anySimpleState(wb_run_step) as wb_run_step,
    anySimpleState(wb_run_step_end) as wb_run_step_end,
    anySimpleStateIf(wb_user_id, isNotNull(call_parts.started_at)) as wb_user_id,
    anySimpleState(trace_id) as trace_id,
    anySimpleState(parent_id) as parent_id,
    anySimpleState(thread_id) as thread_id,
    anySimpleState(turn_id) as turn_id,
    anySimpleState(op_name) as op_name,
    anySimpleState(started_at) as started_at,
    anySimpleState(attributes_dump) as attributes_dump,
    anySimpleState(inputs_dump) as inputs_dump,
    array_concat_aggSimpleState(input_refs) as input_refs,
    anySimpleState(ended_at) as ended_at,
    anySimpleState(output_dump) as output_dump,
    anySimpleState(summary_dump) as summary_dump,
    anySimpleState(exception) as exception,
    array_concat_aggSimpleState(output_refs) as output_refs,
    anySimpleState(deleted_at) as deleted_at,
    argMaxState(display_name, call_parts.created_at) as display_name,
    anySimpleState(coalesce(call_parts.started_at, call_parts.ended_at, call_parts.created_at)) as sortable_datetime,
    anySimpleState(otel_dump) as otel_dump
FROM call_parts
GROUP BY project_id,
    id;

-- ============================================================================
-- object_versions
-- ============================================================================
CREATE TABLE object_versions (
    project_id String,
    object_id String,
    kind Enum('op', 'object'),
    base_object_class String NULL,
    refs Array(String),
    val_dump String,
    digest String,
    created_at DateTime64(3) DEFAULT now64(3),
    deleted_at Nullable(DateTime64(3)) DEFAULT NULL,
    wb_user_id Nullable(String) DEFAULT NULL,
    leaf_object_class Nullable(String) DEFAULT NULL
) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, kind, object_id, digest);

CREATE VIEW object_versions_deduped AS
SELECT project_id,
    object_id,
    created_at,
    deleted_at,
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

-- ============================================================================
-- table_rows
-- ============================================================================
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

-- ============================================================================
-- tables
-- ============================================================================
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

-- ============================================================================
-- files
-- NOTE: The view must be created BEFORE adding the extra columns so that its
-- SELECT * captures only the original column list (matching the sequential
-- migration behavior where 011 added columns after the view existed).
-- ============================================================================
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

ALTER TABLE files ADD COLUMN bytes_stored Nullable(UInt32);
ALTER TABLE files ADD COLUMN file_storage_uri Nullable(String);

-- ============================================================================
-- feedback
-- ============================================================================
CREATE TABLE feedback (
    id String,
    project_id String,
    weave_ref String,
    wb_user_id String,
    creator String NULL,
    created_at DateTime64(3) DEFAULT now64(3),
    feedback_type String,
    payload_dump String,
    annotation_ref Nullable(String) DEFAULT NULL,
    runnable_ref Nullable(String) DEFAULT NULL,
    call_ref Nullable(String) DEFAULT NULL,
    trigger_ref Nullable(String) DEFAULT NULL,
    queue_id Nullable(String) DEFAULT NULL
) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, weave_ref, wb_user_id, id);

-- ============================================================================
-- llm_token_prices
-- ============================================================================
CREATE TABLE llm_token_prices (
    id String,
    pricing_level String,
    pricing_level_id String,
    provider_id String,
    llm_id String,
    effective_date DateTime64(3) DEFAULT now64(3),
    prompt_token_cost Float,
    prompt_token_cost_unit String,
    completion_token_cost Float,
    completion_token_cost_unit String,
    created_by String,
    created_at DateTime64(3) DEFAULT now64(3),
    cache_read_input_token_cost Float DEFAULT 0,
    cache_creation_input_token_cost Float DEFAULT 0
) ENGINE = MergeTree()
ORDER BY (pricing_level, pricing_level_id, provider_id, llm_id, effective_date);

-- ============================================================================
-- Stats: files_stats
-- ============================================================================
CREATE TABLE files_stats (
    project_id String,
    digest String,
    chunk_index UInt32,
    n_chunks SimpleAggregateFunction(any, UInt32),
    name SimpleAggregateFunction(any, String),
    size_bytes SimpleAggregateFunction(any, UInt64),
    created_at SimpleAggregateFunction(min, DateTime64(3)),
    updated_at SimpleAggregateFunction(max, DateTime64(3)),
    file_storage_uri Nullable(String)
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, digest, chunk_index);

CREATE MATERIALIZED VIEW files_stats_view
TO files_stats AS
SELECT
    files.project_id,
    files.digest,
    files.chunk_index,
    anySimpleState(files.n_chunks) as n_chunks,
    anySimpleState(files.name) as name,
    anySimpleState(IF(files.bytes_stored IS NOT NULL, files.bytes_stored, length(files.val_bytes))) AS size_bytes,
    anySimpleState(files.file_storage_uri) AS file_storage_uri,
    minSimpleState(files.created_at) AS created_at,
    maxSimpleState(files.created_at) AS updated_at
FROM files
GROUP BY
    files.project_id,
    files.digest,
    files.chunk_index;

-- ============================================================================
-- Stats: table_rows_stats
-- ============================================================================
CREATE TABLE table_rows_stats (
    project_id String,
    digest String,
    size_bytes SimpleAggregateFunction(any, UInt64),
    created_at SimpleAggregateFunction(min, DateTime64(3)),
    updated_at SimpleAggregateFunction(max, DateTime64(3))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, digest);

CREATE MATERIALIZED VIEW table_rows_stats_view
TO table_rows_stats AS
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

-- ============================================================================
-- Stats: object_versions_stats
-- ============================================================================
CREATE TABLE object_versions_stats (
    project_id String,
    kind Enum('op', 'object'),
    object_id String,
    digest String,
    base_object_class SimpleAggregateFunction(any, Nullable(String)),
    size_bytes SimpleAggregateFunction(any, UInt64),
    created_at SimpleAggregateFunction(min, DateTime64(3)),
    updated_at SimpleAggregateFunction(max, DateTime64(3)),
    wb_user_id Nullable(String) DEFAULT NULL,
    leaf_object_class SimpleAggregateFunction(any, Nullable(String))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, kind, object_id, digest);

CREATE MATERIALIZED VIEW object_versions_stats_view
TO object_versions_stats AS
SELECT
    object_versions.project_id,
    object_versions.kind,
    object_versions.object_id,
    object_versions.digest,
    anySimpleState(object_versions.base_object_class) AS base_object_class,
    anySimpleState(object_versions.leaf_object_class) AS leaf_object_class,
    anySimpleState(object_versions.wb_user_id) AS wb_user_id,
    anySimpleState(length(object_versions.val_dump)) AS size_bytes,
    minSimpleState(object_versions.created_at) AS created_at,
    maxSimpleState(object_versions.created_at) AS updated_at
FROM object_versions
GROUP BY
    object_versions.project_id,
    object_versions.kind,
    object_versions.object_id,
    object_versions.digest;

-- ============================================================================
-- Stats: feedback_stats
-- ============================================================================
CREATE TABLE feedback_stats (
    project_id String,
    weave_ref String,
    wb_user_id String,
    id String,
    creator SimpleAggregateFunction(any, Nullable(String)),
    created_at SimpleAggregateFunction(min, DateTime64(3)),
    updated_at SimpleAggregateFunction(max, DateTime64(3)),
    feedback_type SimpleAggregateFunction(any, String),
    payload_size_bytes SimpleAggregateFunction(any, UInt64)
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, weave_ref, wb_user_id, id);

CREATE MATERIALIZED VIEW feedback_stats_view
TO feedback_stats AS
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

-- ============================================================================
-- Stats: calls_merged_stats
-- ============================================================================
CREATE TABLE calls_merged_stats (
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
    display_name AggregateFunction(argMax, Nullable(String), DateTime64(3)),
    wb_run_step SimpleAggregateFunction(any, Nullable(UInt64)),
    thread_id SimpleAggregateFunction(any, Nullable(String)),
    turn_id SimpleAggregateFunction(any, Nullable(String)),
    wb_run_step_end SimpleAggregateFunction(any, Nullable(UInt64)),
    otel_dump_size_bytes SimpleAggregateFunction(any, Nullable(UInt64))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, id);

CREATE MATERIALIZED VIEW calls_merged_stats_view
TO calls_merged_stats AS
SELECT
    call_parts.project_id,
    call_parts.id,
    anySimpleState(call_parts.trace_id) as trace_id,
    anySimpleState(call_parts.parent_id) as parent_id,
    anySimpleState(call_parts.thread_id) as thread_id,
    anySimpleState(call_parts.turn_id) as turn_id,
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
    anySimpleState(call_parts.wb_run_step) as wb_run_step,
    anySimpleState(call_parts.wb_run_step_end) as wb_run_step_end,
    anySimpleState(call_parts.deleted_at) as deleted_at,
    maxSimpleState(call_parts.created_at) as updated_at,
    argMaxState(call_parts.display_name, call_parts.created_at) as display_name,
    anySimpleState(length(call_parts.otel_dump)) as otel_dump_size_bytes
FROM call_parts
GROUP BY
    call_parts.project_id,
    call_parts.id;

-- ============================================================================
-- calls_complete (v2 schema with bloom filter index)
-- ============================================================================
CREATE TABLE calls_complete (
    id              String,
    project_id      String,
    created_at      DateTime64(3) DEFAULT now64(3),
    trace_id        String,
    op_name         String,
    started_at      DateTime64(6),
    ended_at        DateTime64(6) DEFAULT toDateTime64(0, 6),
    updated_at      DateTime64(3) DEFAULT toDateTime64(0, 3),
    deleted_at      DateTime64(3) DEFAULT toDateTime64(0, 3),
    parent_id       String DEFAULT '',
    display_name    String DEFAULT '',
    exception       String DEFAULT '',
    otel_dump       String DEFAULT '',
    wb_user_id      String DEFAULT '',
    wb_run_id       String DEFAULT '',
    thread_id       String DEFAULT '',
    turn_id         String DEFAULT '',
    inputs_dump     String,
    input_refs      Array(String),
    output_dump     String,
    summary_dump    String,
    output_refs     Array(String),
    attributes_dump String,
    wb_run_step     UInt64 DEFAULT 0,
    wb_run_step_end UInt64 DEFAULT 0,
    ttl_at          DateTime DEFAULT '2100-01-01 00:00:00',
    source          Enum8('direct' = 1, 'dual' = 2, 'migration' = 3) DEFAULT 'direct',
    INDEX idx_parent_id parent_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_inputs_dump inputs_dump TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    INDEX idx_output_dump output_dump TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    INDEX idx_summary_dump summary_dump TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    INDEX idx_wb_run_id wb_run_id TYPE set(100) GRANULARITY 4,
    INDEX idx_thread_id thread_id TYPE set(100) GRANULARITY 4,
    INDEX idx_op_name op_name TYPE ngrambf_v1(8, 10000, 3, 0) GRANULARITY 1,
    INDEX idx_ended_at ended_at TYPE minmax GRANULARITY 1,
    INDEX idx_id id TYPE minmax GRANULARITY 1,
    INDEX idx_id_bloom id TYPE bloom_filter(0.01) GRANULARITY 1
) ENGINE = ReplacingMergeTree(created_at)
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, started_at, id)
TTL ttl_at DELETE
SETTINGS
    min_bytes_for_wide_part=0,
    enable_block_number_column=1,
    enable_block_offset_column=1;

CREATE TABLE calls_complete_stats (
    project_id String,
    id String,
    trace_id SimpleAggregateFunction(any, String),
    parent_id SimpleAggregateFunction(any, String),
    op_name SimpleAggregateFunction(any, String),
    started_at SimpleAggregateFunction(any, DateTime64(6)),
    ended_at SimpleAggregateFunction(any, DateTime64(6)),
    attributes_size_bytes SimpleAggregateFunction(any, UInt64),
    inputs_size_bytes SimpleAggregateFunction(any, UInt64),
    output_size_bytes SimpleAggregateFunction(any, UInt64),
    summary_size_bytes SimpleAggregateFunction(any, UInt64),
    otel_size_bytes SimpleAggregateFunction(any, UInt64),
    exception_size_bytes SimpleAggregateFunction(any, UInt64),
    wb_user_id SimpleAggregateFunction(any, String),
    wb_run_id SimpleAggregateFunction(any, String),
    wb_run_step SimpleAggregateFunction(any, UInt64),
    wb_run_step_end SimpleAggregateFunction(any, UInt64),
    thread_id SimpleAggregateFunction(any, String),
    turn_id SimpleAggregateFunction(any, String),
    created_at SimpleAggregateFunction(min, DateTime64(3)),
    updated_at SimpleAggregateFunction(max, DateTime64(3)),
    display_name AggregateFunction(argMax, String, DateTime64(3))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, id);

CREATE MATERIALIZED VIEW calls_complete_stats_view
TO calls_complete_stats AS
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

-- ============================================================================
-- Annotation system
-- ============================================================================
CREATE TABLE annotation_queues (
    id String,
    project_id String,
    name String,
    description String,
    scorer_refs Array(String),
    created_at DateTime64(3) DEFAULT now64(3),
    created_by String,
    updated_at DateTime64(3) DEFAULT now64(3),
    deleted_at Nullable(DateTime64(3)),
    INDEX idx_created_by created_by TYPE minmax GRANULARITY 1
) ENGINE = MergeTree()
ORDER BY (project_id, id)
SETTINGS
    enable_block_number_column = 1,
    enable_block_offset_column = 1;

CREATE TABLE annotation_queue_items (
    id String,
    project_id String,
    queue_id String,
    call_id String,
    call_started_at DateTime64(3),
    call_ended_at Nullable(DateTime64(3)),
    call_op_name String,
    call_trace_id String,
    display_fields Array(String),
    added_by Nullable(String),
    created_at DateTime64(3) DEFAULT now64(3),
    created_by String,
    updated_at DateTime64(3) DEFAULT now64(3),
    deleted_at Nullable(DateTime64(3))
) ENGINE = MergeTree()
ORDER BY (project_id, queue_id, id)
SETTINGS
    enable_block_number_column = 1,
    enable_block_offset_column = 1;

CREATE TABLE annotator_queue_items_progress (
    id String,
    project_id String,
    queue_item_id String,
    queue_id String,
    annotator_id String,
    annotation_state Enum8(
        'unstarted' = 0,
        'in_progress' = 1,
        'completed' = 2,
        'skipped' = 3
    ) DEFAULT 'unstarted',
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    deleted_at Nullable(DateTime64(3))
) ENGINE = MergeTree()
ORDER BY (project_id, queue_id, id)
SETTINGS
    enable_block_number_column = 1,
    enable_block_offset_column = 1;

-- ============================================================================
-- Tags and aliases
-- ============================================================================
CREATE TABLE IF NOT EXISTS tags (
    project_id String,
    object_id String,
    digest String,
    tag String,
    wb_user_id String DEFAULT '',
    created_at DateTime64(3) DEFAULT now64(3),
    deleted_at DateTime64(3) DEFAULT toDateTime64(0, 3)
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (project_id, object_id, digest, tag)
SETTINGS
    min_bytes_for_wide_part=0,
    enable_block_number_column=1,
    enable_block_offset_column=1;

CREATE TABLE IF NOT EXISTS aliases (
    project_id String,
    object_id String,
    alias String,
    digest String,
    wb_user_id String DEFAULT '',
    created_at DateTime64(3) DEFAULT now64(3),
    deleted_at DateTime64(3) DEFAULT toDateTime64(0, 3)
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (project_id, object_id, alias)
SETTINGS
    min_bytes_for_wide_part=0,
    enable_block_number_column=1,
    enable_block_offset_column=1;

-- ============================================================================
-- object_version_first_seen
-- ============================================================================
CREATE TABLE IF NOT EXISTS object_version_first_seen (
    project_id String,
    object_id String,
    digest String,
    first_created_at SimpleAggregateFunction(min, DateTime64(3))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, object_id, digest);

CREATE MATERIALIZED VIEW IF NOT EXISTS object_version_first_seen_view
TO object_version_first_seen AS
SELECT
    project_id,
    object_id,
    digest,
    minSimpleState(created_at) AS first_created_at
FROM object_versions
GROUP BY project_id, object_id, digest;
