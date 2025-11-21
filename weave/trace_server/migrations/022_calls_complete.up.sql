CREATE TABLE calls_complete (
    id              String,
    project_id      String,
    created_at      DateTime64(3) DEFAULT now64(3),

    trace_id        String,
    op_name         String,
    started_at      DateTime64(6),
    ended_at        Nullable(DateTime64(6)),

    updated_at      Nullable(DateTime64(3)),
    deleted_at      Nullable(DateTime64(3)),

    parent_id       Nullable(String),
    display_name    Nullable(String),

    attributes_dump String,
    inputs_dump     String,
    input_refs      Array(String),
    output_dump     String,
    summary_dump    String,
    otel_dump       Nullable(String),
    exception       Nullable(String),
    output_refs     Array(String),

    wb_user_id      Nullable(String),
    wb_run_id       Nullable(String),
    wb_run_step     Nullable(UInt64),
    wb_run_step_end Nullable(UInt64),

    thread_id       Nullable(String),
    turn_id         Nullable(String),

    -- Bloom filter for needle in the haystack searches
    INDEX idx_parent_id parent_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter GRANULARITY 1,
    -- More conservative bloom filter with explicit small tokenization for
    -- larger JSON dump fields. 32KB per granule, ~4GB index size per 1B rows
    INDEX idx_inputs_dump inputs_dump TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    INDEX idx_output_dump output_dump TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    INDEX idx_attributes_dump attributes_dump TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    -- Set for equality searches with low cardinality ids, high granularity for
    -- smaller index memory size
    INDEX idx_wb_run_id wb_run_id TYPE set(100) GRANULARITY 4,
    INDEX idx_thread_id thread_id TYPE set(100) GRANULARITY 4,
    -- Use ngram so that we can take prefixes of the op_name
    INDEX idx_op_name op_name TYPE ngrambf_v1(8, 10000, 3, 0) GRANULARITY 1,
    -- Minmax for range searches
    INDEX idx_ended_at ended_at TYPE minmax GRANULARITY 1,
    INDEX idx_id id TYPE minmax GRANULARITY 1
) ENGINE = MergeTree
ORDER BY (project_id, started_at, id)
SETTINGS
    -- Required for lightweight updates
    enable_block_number_column=1,
    enable_block_offset_column=1;


CREATE TABLE calls_complete_stats
(
    project_id String,
    id String,
    trace_id SimpleAggregateFunction(any, String),
    parent_id SimpleAggregateFunction(any, Nullable(String)),
    op_name SimpleAggregateFunction(any, String),
    started_at SimpleAggregateFunction(any, DateTime64(6)),
    ended_at SimpleAggregateFunction(any, Nullable(DateTime64(6))),
    attributes_size_bytes SimpleAggregateFunction(any, UInt64),
    inputs_size_bytes SimpleAggregateFunction(any, UInt64),
    output_size_bytes SimpleAggregateFunction(any, UInt64),
    summary_size_bytes SimpleAggregateFunction(any, UInt64),
    otel_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    exception_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    wb_user_id SimpleAggregateFunction(any, Nullable(String)),
    wb_run_id SimpleAggregateFunction(any, Nullable(String)),
    wb_run_step SimpleAggregateFunction(any, Nullable(UInt64)),
    wb_run_step_end SimpleAggregateFunction(any, Nullable(UInt64)),
    thread_id SimpleAggregateFunction(any, Nullable(String)),
    turn_id SimpleAggregateFunction(any, Nullable(String)),
    created_at SimpleAggregateFunction(min, DateTime64(3)),
    updated_at SimpleAggregateFunction(max, Nullable(DateTime64(3))),
    display_name AggregateFunction(argMax, Nullable(String), DateTime64(3))
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
