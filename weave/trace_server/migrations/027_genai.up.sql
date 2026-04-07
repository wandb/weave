-- GenAI Observability Schema (v2 — April 2026)
-- Design doc: docs/design/agents/genai_observability_design.md
--
-- Key design choices:
--   - ReplacingMergeTree for genai_spans (OTel retry handling, no ingest-time dedup)
--   - custom_attrs Map(String, String) instead of EAV table
--   - SummingMergeTree MVs for agents, agent_versions, conversations, traces
--   - genai_message_search for full-text search with deduplication

-- ---------------------------------------------------------------------------
-- 1. genai_spans — primary storage
-- ---------------------------------------------------------------------------
CREATE TABLE genai_spans (
    project_id          String,
    trace_id            String,
    span_id             String,
    parent_span_id      String DEFAULT '',
    span_name           String,
    span_kind           Enum8('UNSPECIFIED'=0,'INTERNAL'=1,'SERVER'=2,'CLIENT'=3,'PRODUCER'=4,'CONSUMER'=5),

    started_at          DateTime64(6),
    ended_at            DateTime64(6) DEFAULT toDateTime64(0, 6),
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
    total_tokens        UInt64 DEFAULT 0,
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
        role String, content String, parts String,
        tool_calls String, finish_reason String, name String
    )) DEFAULT [],
    output_messages Array(Tuple(
        role String, content String, parts String,
        tool_calls String, finish_reason String, name String
    )) DEFAULT [],
    system_instructions Array(String) DEFAULT [],

    tool_call_arguments String DEFAULT '',
    tool_call_result    String DEFAULT '',

    compaction_summary       String DEFAULT '',
    compaction_items_before  UInt32 DEFAULT 0,
    compaction_items_after   UInt32 DEFAULT 0,

    content_refs        Array(String),
    artifact_refs       Array(String),
    object_refs         Array(String),

    custom_attrs        Map(String, String),

    server_address      String DEFAULT '',
    server_port         UInt32 DEFAULT 0,

    attributes_dump     String DEFAULT '',
    events_dump         String DEFAULT '',
    resource_dump       String DEFAULT '',

    wb_user_id          String DEFAULT '',

    INDEX idx_span_id       span_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_trace_id      trace_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_parent        parent_span_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_conv          conversation_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_op            operation_name TYPE set(20) GRANULARITY 4,
    INDEX idx_provider      provider_name TYPE set(20) GRANULARITY 4,
    INDEX idx_agent         agent_name TYPE set(100) GRANULARITY 4,
    INDEX idx_model         request_model TYPE set(100) GRANULARITY 4,
    INDEX idx_tool          tool_name TYPE set(100) GRANULARITY 4,
    INDEX idx_error_type    error_type TYPE set(50) GRANULARITY 4,
    INDEX idx_custom_keys   mapKeys(custom_attrs) TYPE bloom_filter GRANULARITY 1
) ENGINE = ReplacingMergeTree(created_at)
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, started_at, span_id)
SETTINGS min_bytes_for_wide_part=0, enable_block_number_column=1, enable_block_offset_column=1;


-- ---------------------------------------------------------------------------
-- 2. genai_traces — trace time-bound oracle + list page (MV)
-- ---------------------------------------------------------------------------
CREATE TABLE genai_traces (
    project_id String, trace_id String,
    span_count UInt64 DEFAULT 0,
    total_input_tokens UInt64 DEFAULT 0,
    total_output_tokens UInt64 DEFAULT 0,
    error_count UInt64 DEFAULT 0,
    conversation_id SimpleAggregateFunction(max, String),
    agent_name SimpleAggregateFunction(max, String),
    agent_version SimpleAggregateFunction(max, String),
    request_model SimpleAggregateFunction(max, String),
    first_seen SimpleAggregateFunction(min, DateTime64(6)),
    last_seen SimpleAggregateFunction(max, DateTime64(6))
) ENGINE = SummingMergeTree((span_count, total_input_tokens, total_output_tokens, error_count))
ORDER BY (project_id, trace_id);

CREATE MATERIALIZED VIEW genai_traces_mv TO genai_traces AS
SELECT project_id, trace_id,
    toUInt64(1) AS span_count,
    toUInt64(input_tokens) AS total_input_tokens,
    toUInt64(output_tokens) AS total_output_tokens,
    toUInt64(status_code = 'ERROR') AS error_count,
    conversation_id, agent_name, agent_version, request_model,
    started_at AS first_seen, started_at AS last_seen
FROM genai_spans;


-- ---------------------------------------------------------------------------
-- 3. genai_agents — per-agent aggregated stats (MV)
-- ---------------------------------------------------------------------------
CREATE TABLE genai_agents (
    project_id String, agent_name String,
    invocation_count UInt64 DEFAULT 0, span_count UInt64 DEFAULT 0,
    total_input_tokens UInt64 DEFAULT 0, total_output_tokens UInt64 DEFAULT 0,
    total_duration_ms UInt64 DEFAULT 0, error_count UInt64 DEFAULT 0,
    agent_description SimpleAggregateFunction(max, String),
    agent_id SimpleAggregateFunction(max, String),
    provider_name SimpleAggregateFunction(max, String),
    first_seen SimpleAggregateFunction(min, DateTime64(6)),
    last_seen SimpleAggregateFunction(max, DateTime64(6)),
    llm_summary SimpleAggregateFunction(max, String),
    llm_summary_updated_at DateTime64(6) DEFAULT toDateTime64(0, 6),
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = SummingMergeTree((invocation_count, span_count, total_input_tokens, total_output_tokens, total_duration_ms, error_count))
ORDER BY (project_id, agent_name);

CREATE MATERIALIZED VIEW genai_agents_mv TO genai_agents AS
SELECT project_id, agent_name,
    toUInt64(operation_name = 'invoke_agent') AS invocation_count,
    toUInt64(1) AS span_count,
    toUInt64(input_tokens) AS total_input_tokens,
    toUInt64(output_tokens) AS total_output_tokens,
    toUInt64(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)) AS total_duration_ms,
    toUInt64(status_code = 'ERROR') AS error_count,
    agent_description, agent_id, provider_name,
    started_at AS first_seen, started_at AS last_seen,
    '' AS llm_summary, toDateTime64(0, 6) AS llm_summary_updated_at
FROM genai_spans WHERE agent_name != '';


-- ---------------------------------------------------------------------------
-- 4. genai_agent_versions — per-version drill-down (MV)
-- ---------------------------------------------------------------------------
CREATE TABLE genai_agent_versions (
    project_id String, agent_name String, agent_version String,
    invocation_count UInt64 DEFAULT 0, span_count UInt64 DEFAULT 0,
    total_input_tokens UInt64 DEFAULT 0, total_output_tokens UInt64 DEFAULT 0,
    total_duration_ms UInt64 DEFAULT 0, error_count UInt64 DEFAULT 0,
    agent_description SimpleAggregateFunction(max, String),
    agent_id SimpleAggregateFunction(max, String),
    provider_name SimpleAggregateFunction(max, String),
    first_seen SimpleAggregateFunction(min, DateTime64(6)),
    last_seen SimpleAggregateFunction(max, DateTime64(6)),
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = SummingMergeTree((invocation_count, span_count, total_input_tokens, total_output_tokens, total_duration_ms, error_count))
ORDER BY (project_id, agent_name, agent_version);

CREATE MATERIALIZED VIEW genai_agent_versions_mv TO genai_agent_versions AS
SELECT project_id, agent_name, agent_version,
    toUInt64(operation_name = 'invoke_agent') AS invocation_count,
    toUInt64(1) AS span_count,
    toUInt64(input_tokens) AS total_input_tokens,
    toUInt64(output_tokens) AS total_output_tokens,
    toUInt64(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)) AS total_duration_ms,
    toUInt64(status_code = 'ERROR') AS error_count,
    agent_description, agent_id, provider_name,
    started_at AS first_seen, started_at AS last_seen
FROM genai_spans WHERE agent_name != '';


-- ---------------------------------------------------------------------------
-- 5. genai_conversations — per-conversation aggregated stats (MV)
-- ---------------------------------------------------------------------------
CREATE TABLE genai_conversations (
    project_id String, conversation_id String,
    turn_count UInt64 DEFAULT 0, span_count UInt64 DEFAULT 0,
    total_input_tokens UInt64 DEFAULT 0, total_output_tokens UInt64 DEFAULT 0,
    total_duration_ms UInt64 DEFAULT 0, error_count UInt64 DEFAULT 0,
    conversation_name SimpleAggregateFunction(max, String),
    agent_name SimpleAggregateFunction(max, String),
    agent_version SimpleAggregateFunction(max, String),
    provider_name SimpleAggregateFunction(max, String),
    first_seen SimpleAggregateFunction(min, DateTime64(6)),
    last_seen SimpleAggregateFunction(max, DateTime64(6)),
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = SummingMergeTree((turn_count, span_count, total_input_tokens, total_output_tokens, total_duration_ms, error_count))
ORDER BY (project_id, conversation_id);

CREATE MATERIALIZED VIEW genai_conversations_mv TO genai_conversations AS
SELECT project_id, conversation_id,
    toUInt64(operation_name = 'invoke_agent') AS turn_count,
    toUInt64(1) AS span_count,
    toUInt64(input_tokens) AS total_input_tokens,
    toUInt64(output_tokens) AS total_output_tokens,
    toUInt64(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)) AS total_duration_ms,
    toUInt64(status_code = 'ERROR') AS error_count,
    conversation_name, agent_name, agent_version, provider_name,
    started_at AS first_seen, started_at AS last_seen
FROM genai_spans WHERE conversation_id != '';


-- ---------------------------------------------------------------------------
-- 6. genai_conversation_traces — conversation→trace mapping (MV)
-- ---------------------------------------------------------------------------
CREATE TABLE genai_conversation_traces (
    project_id String, conversation_id String, trace_id String,
    first_seen SimpleAggregateFunction(min, DateTime64(6)),
    last_seen SimpleAggregateFunction(max, DateTime64(6)),
    span_count UInt64 DEFAULT 0
) ENGINE = SummingMergeTree(span_count)
ORDER BY (project_id, conversation_id, trace_id);

CREATE MATERIALIZED VIEW genai_conversation_traces_mv TO genai_conversation_traces AS
SELECT project_id, conversation_id, trace_id,
    started_at AS first_seen, started_at AS last_seen,
    toUInt64(1) AS span_count
FROM genai_spans WHERE conversation_id != '';


-- ---------------------------------------------------------------------------
-- 7. genai_message_search — per-message full-text search
-- ---------------------------------------------------------------------------
CREATE TABLE genai_message_search (
    project_id String, content_digest String,
    conversation_id String DEFAULT '', trace_id String, span_id String,
    role String DEFAULT '', started_at DateTime64(6),
    content String,
    agent_name String DEFAULT '', agent_version String DEFAULT '',
    conversation_name String DEFAULT '', wb_user_id String DEFAULT '',
    provider_name String DEFAULT '', request_model String DEFAULT '',
    operation_name String DEFAULT '',
    created_at DateTime64(3) DEFAULT now64(3),
    INDEX idx_content content TYPE ngrambf_v1(3, 512, 2, 0) GRANULARITY 1,
    INDEX idx_agent agent_name TYPE ngrambf_v1(3, 256, 2, 0) GRANULARITY 1,
    INDEX idx_conv_name conversation_name TYPE ngrambf_v1(3, 256, 2, 0) GRANULARITY 1,
    INDEX idx_role role TYPE set(10) GRANULARITY 4,
    INDEX idx_conv_id conversation_id TYPE set(100) GRANULARITY 4,
    INDEX idx_trace_id trace_id TYPE bloom_filter GRANULARITY 1
) ENGINE = ReplacingMergeTree(created_at)
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, content_digest)
SETTINGS min_bytes_for_wide_part = 0;
