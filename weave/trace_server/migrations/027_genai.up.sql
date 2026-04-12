-- GenAI Observability Schema v4
--
-- 3 core tables, 2 MVs + optional message search:
--   1. genai_spans          — MergeTree, bloom filters, codecs, typed Maps
--   2. genai_agents         — AggregatingMergeTree MV, lean counters + first/last seen
--   3. genai_agent_versions — AggregatingMergeTree MV, same pattern
--   4. genai_message_search — app-level insert, full-text search (optional)
--
-- No skinny table, no projections.
-- ReplacingMergeTree(created_at) for idempotent re-inserts / late updates.
-- Monthly partitioning for time-range pruning and TTL-based retention.
-- ClickHouse columnar storage means queries only read the columns they SELECT.
-- Bloom filters on IDs for point lookups, ngrambf on dimensions for substring search.
-- All span-derived queries use time bounds from the UI (H/D/W/M presets).
-- AMTs handle the only all-time queries: agent/version aggregate counters.
--
-- See: benchmarks/genai_clickhouse/REPORT.md for design rationale.

-- ---------------------------------------------------------------------------
-- 1. genai_spans — primary storage
-- ---------------------------------------------------------------------------
CREATE TABLE genai_spans (
    project_id          String CODEC(ZSTD(1)),
    trace_id            String CODEC(ZSTD(1)),
    span_id             String CODEC(ZSTD(1)),
    parent_span_id      String DEFAULT '' CODEC(ZSTD(1)),
    span_name           String CODEC(ZSTD(1)),
    span_kind           Enum8('UNSPECIFIED'=0,'INTERNAL'=1,'SERVER'=2,'CLIENT'=3,'PRODUCER'=4,'CONSUMER'=5) CODEC(ZSTD(1)),

    started_at          DateTime64(6) CODEC(Delta(8), ZSTD(1)),
    ended_at            DateTime64(6) DEFAULT toDateTime64(0, 6) CODEC(Delta(8), ZSTD(1)),
    created_at          DateTime64(3) DEFAULT now64(3) CODEC(Delta(8), ZSTD(1)),

    status_code         Enum8('UNSET'=0,'OK'=1,'ERROR'=2) CODEC(ZSTD(1)),
    status_message      String DEFAULT '' CODEC(ZSTD(1)),

    operation_name      String DEFAULT '' CODEC(ZSTD(1)),
    provider_name       String DEFAULT '' CODEC(ZSTD(1)),

    agent_name          String DEFAULT '' CODEC(ZSTD(1)),
    agent_id            String DEFAULT '' CODEC(ZSTD(1)),
    agent_description   String DEFAULT '' CODEC(ZSTD(1)),
    agent_version       String DEFAULT '' CODEC(ZSTD(1)),

    request_model       String DEFAULT '' CODEC(ZSTD(1)),
    response_model      String DEFAULT '' CODEC(ZSTD(1)),
    response_id         String DEFAULT '' CODEC(ZSTD(1)),
    input_tokens        UInt64 DEFAULT 0 CODEC(ZSTD(1)),
    output_tokens       UInt64 DEFAULT 0 CODEC(ZSTD(1)),
    total_tokens        UInt64 DEFAULT 0 CODEC(ZSTD(1)),
    reasoning_tokens    UInt64 DEFAULT 0 CODEC(ZSTD(1)),
    cache_creation_input_tokens UInt64 DEFAULT 0 CODEC(ZSTD(1)),
    cache_read_input_tokens     UInt64 DEFAULT 0 CODEC(ZSTD(1)),

    reasoning_content   String DEFAULT '' CODEC(ZSTD(1)),

    conversation_id     String DEFAULT '' CODEC(ZSTD(1)),
    conversation_name   String DEFAULT '' CODEC(ZSTD(1)),

    tool_name           String DEFAULT '' CODEC(ZSTD(1)),
    tool_type           String DEFAULT '' CODEC(ZSTD(1)),
    tool_call_id        String DEFAULT '' CODEC(ZSTD(1)),
    tool_description    String DEFAULT '' CODEC(ZSTD(1)),
    tool_definitions    String DEFAULT '' CODEC(ZSTD(1)),

    finish_reasons      Array(String) CODEC(ZSTD(1)),
    error_type          String DEFAULT '' CODEC(ZSTD(1)),

    request_temperature     Float64 DEFAULT 0 CODEC(ZSTD(1)),
    request_max_tokens      UInt64 DEFAULT 0 CODEC(ZSTD(1)),
    request_top_p           Float64 DEFAULT 0 CODEC(ZSTD(1)),
    request_frequency_penalty Float64 DEFAULT 0 CODEC(ZSTD(1)),
    request_presence_penalty  Float64 DEFAULT 0 CODEC(ZSTD(1)),
    request_seed            Int64 DEFAULT 0 CODEC(ZSTD(1)),
    request_stop_sequences  Array(String) DEFAULT [] CODEC(ZSTD(1)),
    request_choice_count    UInt32 DEFAULT 0 CODEC(ZSTD(1)),

    output_type         String DEFAULT '' CODEC(ZSTD(1)),

    input_messages  Array(Tuple(
        role String, content String, finish_reason String
    )) CODEC(ZSTD(1)),
    output_messages Array(Tuple(
        role String, content String, finish_reason String
    )) CODEC(ZSTD(1)),
    system_instructions Array(String) DEFAULT [] CODEC(ZSTD(1)),

    tool_call_arguments String DEFAULT '' CODEC(ZSTD(1)),
    tool_call_result    String DEFAULT '' CODEC(ZSTD(1)),

    compaction_summary       String DEFAULT '' CODEC(ZSTD(1)),
    compaction_items_before  UInt32 DEFAULT 0 CODEC(ZSTD(1)),
    compaction_items_after   UInt32 DEFAULT 0 CODEC(ZSTD(1)),

    content_refs        Array(String) CODEC(ZSTD(1)),
    artifact_refs       Array(String) CODEC(ZSTD(1)),
    object_refs         Array(String) CODEC(ZSTD(1)),

    custom_attrs        Map(String, String) CODEC(ZSTD(1)),
    custom_attrs_int    Map(String, Int64) CODEC(ZSTD(1)),
    custom_attrs_float  Map(String, Float64) CODEC(ZSTD(1)),

    server_address      String DEFAULT '' CODEC(ZSTD(1)),
    server_port         UInt32 DEFAULT 0 CODEC(ZSTD(1)),

    raw_span_dump       String DEFAULT '' CODEC(ZSTD(1)),
    attributes_dump     String DEFAULT '' CODEC(ZSTD(1)),
    events_dump         String DEFAULT '' CODEC(ZSTD(1)),
    resource_dump       String DEFAULT '' CODEC(ZSTD(1)),

    wb_user_id          String DEFAULT '' CODEC(ZSTD(1)),
    wb_run_id           String DEFAULT '' CODEC(ZSTD(1)),
    wb_run_step         UInt64 DEFAULT 0 CODEC(ZSTD(1)),
    wb_run_step_end     UInt64 DEFAULT 0 CODEC(ZSTD(1)),

    ttl_at              DateTime DEFAULT '2100-01-01 00:00:00' CODEC(ZSTD(1)),

    -- Point lookup bloom filters (high selectivity — ~1 row per ID)
    INDEX idx_span_id span_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_parent parent_span_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_wb_run_id wb_run_id TYPE bloom_filter(0.01) GRANULARITY 1,
    -- Dimension ngrambf indexes (substring search on filtered scans)
    INDEX idx_operation_name operation_name TYPE ngrambf_v1(8, 10000, 3, 0) GRANULARITY 1,
    INDEX idx_provider_name provider_name TYPE ngrambf_v1(8, 10000, 3, 0) GRANULARITY 1,
    INDEX idx_request_model request_model TYPE ngrambf_v1(8, 10000, 3, 0) GRANULARITY 1,
    INDEX idx_response_model response_model TYPE ngrambf_v1(8, 10000, 3, 0) GRANULARITY 1,
    INDEX idx_agent_name agent_name TYPE ngrambf_v1(8, 10000, 3, 0) GRANULARITY 1,
    INDEX idx_agent_version agent_version TYPE ngrambf_v1(8, 10000, 3, 0) GRANULARITY 1,
    INDEX idx_error_type error_type TYPE ngrambf_v1(8, 10000, 3, 0) GRANULARITY 1
) ENGINE = ReplacingMergeTree(created_at)
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, started_at, span_id)
TTL ttl_at DELETE
SETTINGS min_bytes_for_wide_part=0;


-- ---------------------------------------------------------------------------
-- 2. genai_agents — all-time counters + first/last seen
-- ---------------------------------------------------------------------------
CREATE TABLE genai_agents (
    project_id String CODEC(ZSTD(1)),
    agent_name String CODEC(ZSTD(1)),
    invocation_count SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1)),
    span_count SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1)),
    total_input_tokens SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1)),
    total_output_tokens SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1)),
    total_duration_ms SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1)),
    error_count SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1)),
    first_seen SimpleAggregateFunction(min, DateTime64(6)) CODEC(Delta(8), ZSTD(1)),
    last_seen SimpleAggregateFunction(max, DateTime64(6)) CODEC(Delta(8), ZSTD(1))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, agent_name);

CREATE MATERIALIZED VIEW genai_agents_mv TO genai_agents AS
SELECT
    project_id,
    agent_name,
    toUInt64(operation_name = 'invoke_agent') AS invocation_count,
    toUInt64(1) AS span_count,
    toUInt64(input_tokens) AS total_input_tokens,
    toUInt64(output_tokens) AS total_output_tokens,
    toUInt64(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)) AS total_duration_ms,
    toUInt64(status_code = 'ERROR') AS error_count,
    started_at AS first_seen,
    started_at AS last_seen
FROM genai_spans
WHERE agent_name != '';


-- ---------------------------------------------------------------------------
-- 3. genai_agent_versions — all-time counters + first/last seen
-- ---------------------------------------------------------------------------
CREATE TABLE genai_agent_versions (
    project_id String CODEC(ZSTD(1)),
    agent_name String CODEC(ZSTD(1)),
    agent_version String CODEC(ZSTD(1)),
    invocation_count SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1)),
    span_count SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1)),
    total_input_tokens SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1)),
    total_output_tokens SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1)),
    total_duration_ms SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1)),
    error_count SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1)),
    first_seen SimpleAggregateFunction(min, DateTime64(6)) CODEC(Delta(8), ZSTD(1)),
    last_seen SimpleAggregateFunction(max, DateTime64(6)) CODEC(Delta(8), ZSTD(1))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, agent_name, agent_version);

CREATE MATERIALIZED VIEW genai_agent_versions_mv TO genai_agent_versions AS
SELECT
    project_id,
    agent_name,
    agent_version,
    toUInt64(operation_name = 'invoke_agent') AS invocation_count,
    toUInt64(1) AS span_count,
    toUInt64(input_tokens) AS total_input_tokens,
    toUInt64(output_tokens) AS total_output_tokens,
    toUInt64(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)) AS total_duration_ms,
    toUInt64(status_code = 'ERROR') AS error_count,
    started_at AS first_seen,
    started_at AS last_seen
FROM genai_spans
WHERE agent_name != '';


-- ---------------------------------------------------------------------------
-- 4. genai_message_search — per-message full-text search (app-level insert)
-- ---------------------------------------------------------------------------
CREATE TABLE genai_message_search (
    project_id String CODEC(ZSTD(1)),
    content_digest String CODEC(ZSTD(1)),
    conversation_id String DEFAULT '' CODEC(ZSTD(1)),
    trace_id String CODEC(ZSTD(1)),
    span_id String CODEC(ZSTD(1)),
    role String DEFAULT '' CODEC(ZSTD(1)),
    started_at DateTime64(6) CODEC(Delta(8), ZSTD(1)),
    content String CODEC(ZSTD(1)),
    agent_name String DEFAULT '' CODEC(ZSTD(1)),
    agent_version String DEFAULT '' CODEC(ZSTD(1)),
    conversation_name String DEFAULT '' CODEC(ZSTD(1)),
    wb_user_id String DEFAULT '' CODEC(ZSTD(1)),
    provider_name String DEFAULT '' CODEC(ZSTD(1)),
    request_model String DEFAULT '' CODEC(ZSTD(1)),
    operation_name String DEFAULT '' CODEC(ZSTD(1)),
    created_at DateTime64(3) DEFAULT now64(3) CODEC(Delta(8), ZSTD(1)),

    INDEX idx_content content TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    INDEX idx_conv_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (project_id, content_digest)
SETTINGS min_bytes_for_wide_part = 0;
