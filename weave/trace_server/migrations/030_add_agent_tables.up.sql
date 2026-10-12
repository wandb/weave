-- Agent observability tables.

-- spans
CREATE TABLE IF NOT EXISTS spans (
    project_id          String,
    trace_id            String,
    span_id             String,
    parent_span_id      String DEFAULT '',
    span_name           String,
    span_kind           Enum8('UNSPECIFIED'=0,'INTERNAL'=1,'SERVER'=2,'CLIENT'=3,'PRODUCER'=4,'CONSUMER'=5),

    started_at          DateTime64(6),
    ended_at            DateTime64(6) DEFAULT toDateTime64(0, 6),
    -- Python ingest always sends created_at. This DEFAULT is a defensive
    -- fallback for ad hoc inserts/backfills that omit the column.
    created_at          DateTime64(3) DEFAULT now64(3),

    status_code         Enum8('UNSET'=0,'OK'=1,'ERROR'=2),
    status_message      String DEFAULT '',

    operation_name      String DEFAULT '',
    provider_name       String DEFAULT '',

    agent_name          String DEFAULT '',
    agent_id            String DEFAULT '',
    agent_description   String DEFAULT '',
    agent_version       String DEFAULT '',

    request_model       String DEFAULT '',
    response_model      String DEFAULT '',
    response_id         String DEFAULT '',
    input_tokens        UInt64 DEFAULT 0,
    output_tokens       UInt64 DEFAULT 0,
    reasoning_tokens    UInt64 DEFAULT 0,
    cache_creation_input_tokens UInt64 DEFAULT 0,
    cache_read_input_tokens     UInt64 DEFAULT 0,

    reasoning_content   String DEFAULT '',

    conversation_id     String DEFAULT '',
    conversation_name   String DEFAULT '',

    tool_name           String DEFAULT '',
    tool_type           String DEFAULT '',
    tool_call_id        String DEFAULT '',
    tool_description    String DEFAULT '',
    tool_definitions    String DEFAULT '',

    finish_reasons      Array(String),
    error_type          String DEFAULT '',

    request_temperature     Float64 DEFAULT 0,
    request_max_tokens      UInt64 DEFAULT 0,
    request_top_p           Float64 DEFAULT 0,
    request_frequency_penalty Float64 DEFAULT 0,
    request_presence_penalty  Float64 DEFAULT 0,
    request_seed            Int64 DEFAULT 0,
    request_stop_sequences  Array(String) DEFAULT [],
    request_choice_count    UInt32 DEFAULT 0,

    output_type         String DEFAULT '',

    input_messages  Array(Tuple(
        role String, content String, finish_reason String
    )),
    output_messages Array(Tuple(
        role String, content String, finish_reason String
    )),
    system_instructions Array(String) DEFAULT [],

    tool_call_arguments String DEFAULT '',
    tool_call_result    String DEFAULT '',

    compaction_summary       String DEFAULT '',
    compaction_items_before  UInt32 DEFAULT 0,
    compaction_items_after   UInt32 DEFAULT 0,

    content_refs        Array(String),
    artifact_refs       Array(String),
    object_refs         Array(String),

    custom_attrs_string Map(String, String),
    custom_attrs_int    Map(String, Int64),
    custom_attrs_float  Map(String, Float64),
    custom_attrs_bool   Map(String, Bool),

    server_address      String DEFAULT '',
    server_port         UInt32 DEFAULT 0,

    raw_span_dump       String DEFAULT '',
    attributes_dump     String DEFAULT '',
    events_dump         String DEFAULT '',
    resource_dump       String DEFAULT '',

    wb_user_id          String DEFAULT '',
    wb_run_id           String DEFAULT '',
    wb_run_step         UInt64 DEFAULT 0,
    wb_run_step_end     UInt64 DEFAULT 0,

    expire_at              DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_span_id span_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_parent parent_span_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_wb_run_id wb_run_id TYPE bloom_filter(0.01) GRANULARITY 1,
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
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part=0;


-- agents (materialized from spans)
CREATE TABLE IF NOT EXISTS agents (
    project_id String,
    agent_name String,
    invocation_count SimpleAggregateFunction(sum, UInt64),
    span_count SimpleAggregateFunction(sum, UInt64),
    total_input_tokens SimpleAggregateFunction(sum, UInt64),
    total_output_tokens SimpleAggregateFunction(sum, UInt64),
    total_duration_ms SimpleAggregateFunction(sum, UInt64),
    error_count SimpleAggregateFunction(sum, UInt64),
    first_seen SimpleAggregateFunction(min, DateTime64(6)),
    last_seen SimpleAggregateFunction(max, DateTime64(6))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, agent_name);

CREATE MATERIALIZED VIEW IF NOT EXISTS agents_mv TO agents AS
SELECT
    project_id,
    agent_name,
    toUInt64(operation_name = 'invoke_agent') AS invocation_count,
    toUInt64(1) AS span_count,
    toUInt64(input_tokens) AS total_input_tokens,
    toUInt64(output_tokens) AS total_output_tokens,
    -- Guard against spans that never had ended_at set (defaults to epoch).
    -- Without this, toUInt64 on a negative subtraction wraps to ~2^64 and
    -- poisons the SUM aggregate for the agent row forever.
    if(ended_at > started_at,
       toUInt64(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)),
       toUInt64(0)) AS total_duration_ms,
    toUInt64(status_code = 'ERROR') AS error_count,
    started_at AS first_seen,
    started_at AS last_seen
FROM spans
WHERE agent_name != '';


-- agent_versions (materialized from spans)
CREATE TABLE IF NOT EXISTS agent_versions (
    project_id String,
    agent_name String,
    agent_version String,
    invocation_count SimpleAggregateFunction(sum, UInt64),
    span_count SimpleAggregateFunction(sum, UInt64),
    total_input_tokens SimpleAggregateFunction(sum, UInt64),
    total_output_tokens SimpleAggregateFunction(sum, UInt64),
    total_duration_ms SimpleAggregateFunction(sum, UInt64),
    error_count SimpleAggregateFunction(sum, UInt64),
    first_seen SimpleAggregateFunction(min, DateTime64(6)),
    last_seen SimpleAggregateFunction(max, DateTime64(6))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, agent_name, agent_version);

CREATE MATERIALIZED VIEW IF NOT EXISTS agent_versions_mv TO agent_versions AS
SELECT
    project_id,
    agent_name,
    agent_version,
    toUInt64(operation_name = 'invoke_agent') AS invocation_count,
    toUInt64(1) AS span_count,
    toUInt64(input_tokens) AS total_input_tokens,
    toUInt64(output_tokens) AS total_output_tokens,
    -- Guard against spans that never had ended_at set (defaults to epoch).
    -- Without this, toUInt64 on a negative subtraction wraps to ~2^64 and
    -- poisons the SUM aggregate for the agent row forever.
    if(ended_at > started_at,
       toUInt64(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)),
       toUInt64(0)) AS total_duration_ms,
    toUInt64(status_code = 'ERROR') AS error_count,
    started_at AS first_seen,
    started_at AS last_seen
FROM spans
WHERE agent_name != '';


-- messages: one row per (message, span) appearance. Content is stored
-- inline per row (ClickHouse columnar compression handles the duplication
-- of repeated content well). content_digest is materialized at MV time to
-- support read-side dedup via GROUP BY when needed.
--
-- Digest is murmurHash3_128 (128-bit, non-cryptographic) stored raw as
-- FixedString(16). Read-path queries hex-encode it for the Python API.
-- murmurHash3_128 is ~10x faster than SHA256 on the ingest hot path and
-- 128 bits is plenty for per-project content identity. We are not doing
-- cryptography here.
CREATE TABLE IF NOT EXISTS messages (
    project_id        String,
    content_digest    FixedString(16),
    content           String,
    trace_id          String,
    span_id           String,
    parent_span_id    String DEFAULT '',
    conversation_id   String DEFAULT '',
    conversation_name String DEFAULT '',
    agent_name        String DEFAULT '',
    agent_version     String DEFAULT '',
    provider_name     String DEFAULT '',
    request_model     String DEFAULT '',
    operation_name    String DEFAULT '',
    role              String DEFAULT '',
    started_at        DateTime64(6),
    wb_user_id        String DEFAULT '',
    created_at        DateTime64(3) DEFAULT now64(3),

    INDEX idx_content content TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1,
    INDEX idx_digest content_digest TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_span_id span_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conv_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, started_at, span_id)
SETTINGS min_bytes_for_wide_part = 0;


-- One MV per source of message text. All five target the same ``messages``
-- table. Splitting the sources keeps each MV projection simple and avoids
-- building one sparse concatenated array that ARRAY JOIN must explode and
-- filter on every span insert.
CREATE MATERIALIZED VIEW IF NOT EXISTS messages_mv_output_messages TO messages AS
SELECT project_id,
       murmurHash3_128(m.2) AS content_digest,
       m.2 AS content,
       trace_id, span_id, parent_span_id,
       conversation_id, conversation_name, agent_name, agent_version,
       provider_name, request_model, operation_name,
       m.1 AS role,
       started_at,
       wb_user_id
FROM spans ARRAY JOIN output_messages AS m
WHERE m.2 != '';

CREATE MATERIALIZED VIEW IF NOT EXISTS messages_mv_input_messages TO messages AS
SELECT project_id,
       murmurHash3_128(m.2) AS content_digest,
       m.2 AS content,
       trace_id, span_id, parent_span_id,
       conversation_id, conversation_name, agent_name, agent_version,
       provider_name, request_model, operation_name,
       m.1 AS role,
       started_at,
       wb_user_id
FROM spans ARRAY JOIN input_messages AS m
WHERE m.2 != '';

CREATE MATERIALIZED VIEW IF NOT EXISTS messages_mv_system_instructions TO messages AS
SELECT project_id,
       murmurHash3_128(s) AS content_digest,
       s AS content,
       trace_id, span_id, parent_span_id,
       conversation_id, conversation_name, agent_name, agent_version,
       provider_name, request_model, operation_name,
       'system' AS role,
       started_at,
       wb_user_id
FROM spans ARRAY JOIN system_instructions AS s
WHERE s != '';

CREATE MATERIALIZED VIEW IF NOT EXISTS messages_mv_tool_call_arguments TO messages AS
SELECT project_id,
       murmurHash3_128(tool_call_arguments) AS content_digest,
       tool_call_arguments AS content,
       trace_id, span_id, parent_span_id,
       conversation_id, conversation_name, agent_name, agent_version,
       provider_name, request_model, operation_name,
       'tool_call' AS role,
       started_at,
       wb_user_id
FROM spans
WHERE tool_call_arguments != '';

CREATE MATERIALIZED VIEW IF NOT EXISTS messages_mv_tool_call_result TO messages AS
SELECT project_id,
       murmurHash3_128(tool_call_result) AS content_digest,
       tool_call_result AS content,
       trace_id, span_id, parent_span_id,
       conversation_id, conversation_name, agent_name, agent_version,
       provider_name, request_model, operation_name,
       'tool_result' AS role,
       started_at,
       wb_user_id
FROM spans
WHERE tool_call_result != '';
