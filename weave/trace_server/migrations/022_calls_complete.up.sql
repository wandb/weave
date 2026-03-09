-- calls_complete v2 schema
--
-- NOTE: This migration was retroactively updated to create the v2 schema
-- directly (non-nullable sentinels, ReplacingMergeTree, TTL, partitioning).
-- The original v1 schema used Nullable columns and plain MergeTree.
-- Migration 024 handles the v1 -> v2 upgrade for any instances that already
-- ran the original version of this file. For fresh installs, 024's rename
-- dance is harmless on empty tables.

CREATE TABLE calls_complete (
    -- Primary fields
    id              String,
    project_id      String,
    created_at      DateTime64(3) DEFAULT now64(3),
    trace_id        String,
    op_name         String,
    started_at      DateTime64(6),

    -- DateTime fields: sentinel = epoch zero (toDateTime64(0, N))
    ended_at        DateTime64(6) DEFAULT toDateTime64(0, 6),
    updated_at      DateTime64(3) DEFAULT toDateTime64(0, 3),
    deleted_at      DateTime64(3) DEFAULT toDateTime64(0, 3),

    -- String fields: sentinel = '' (empty string)
    parent_id       String DEFAULT '',
    display_name    String DEFAULT '',
    exception       String DEFAULT '',
    otel_dump       String DEFAULT '',
    wb_user_id      String DEFAULT '',
    wb_run_id       String DEFAULT '',
    thread_id       String DEFAULT '',
    turn_id         String DEFAULT '',

    -- Non-nullable data fields
    inputs_dump     String,
    input_refs      Array(String),
    output_dump     String,
    summary_dump    String,
    output_refs     Array(String),

    attributes_dump String,

    -- UInt64 fields: non-nullable, 0 = not set
    wb_run_step     UInt64 DEFAULT 0,
    wb_run_step_end UInt64 DEFAULT 0,

    -- TTL and source tracking
    ttl_at          DateTime DEFAULT '2100-01-01 00:00:00',
    source          Enum8('direct' = 1, 'dual' = 2, 'migration' = 3) DEFAULT 'direct',

    -- Bloom filter for needle in the haystack searches
    INDEX idx_parent_id parent_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter GRANULARITY 1,
    -- More conservative bloom filter with explicit small tokenization for
    -- larger JSON dump fields. 32KB per granule, ~4GB index size per 1B rows
    INDEX idx_inputs_dump inputs_dump TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    INDEX idx_output_dump output_dump TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    INDEX idx_summary_dump summary_dump TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    -- Set for equality searches with low cardinality ids, high granularity for
    -- smaller index memory size
    INDEX idx_wb_run_id wb_run_id TYPE set(100) GRANULARITY 4,
    INDEX idx_thread_id thread_id TYPE set(100) GRANULARITY 4,
    -- Use ngram so that we can take prefixes of the op_name
    INDEX idx_op_name op_name TYPE ngrambf_v1(8, 10000, 3, 0) GRANULARITY 1,
    -- Minmax for range searches
    INDEX idx_ended_at ended_at TYPE minmax GRANULARITY 1,
    INDEX idx_id id TYPE minmax GRANULARITY 1
) ENGINE = ReplacingMergeTree(created_at)
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, started_at, id)
TTL ttl_at DELETE
SETTINGS
    min_bytes_for_wide_part=0,
    enable_block_number_column=1,
    enable_block_offset_column=1;


CREATE TABLE calls_complete_stats
(
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
TO calls_complete_stats
AS
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
