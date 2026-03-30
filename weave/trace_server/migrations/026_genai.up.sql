CREATE TABLE genai_spans (
    -- Core span identity
    project_id          String,
    trace_id            String,
    span_id             String,
    parent_span_id      String DEFAULT '',
    span_name           String,
    span_kind           Enum8('UNSPECIFIED'=0,'INTERNAL'=1,'SERVER'=2,'CLIENT'=3,'PRODUCER'=4,'CONSUMER'=5),

    -- Timestamps
    started_at          DateTime64(6),
    ended_at            DateTime64(6) DEFAULT toDateTime64(0, 6),
    created_at          DateTime64(3) DEFAULT now64(3),

    -- Status
    status_code         Enum8('UNSET'=0,'OK'=1,'ERROR'=2),
    status_message      String DEFAULT '',

    -- GenAI classification (extracted from semconv)
    operation_name      String DEFAULT '',
    provider_name       String DEFAULT '',

    -- Agent info
    agent_name          String DEFAULT '',
    agent_id            String DEFAULT '',
    agent_description   String DEFAULT '',
    agent_version       String DEFAULT '',

    -- Model info
    request_model       String DEFAULT '',
    response_model      String DEFAULT '',
    response_id         String DEFAULT '',

    -- Token usage
    input_tokens        UInt64 DEFAULT 0,
    output_tokens       UInt64 DEFAULT 0,
    total_tokens        UInt64 DEFAULT 0,
    reasoning_tokens    UInt64 DEFAULT 0,

    -- Reasoning content (from ReasoningPart in output messages)
    reasoning_content   String DEFAULT '',

    -- Conversation / session
    conversation_id     String DEFAULT '',
    conversation_name   String DEFAULT '',

    -- Tool info
    tool_name           String DEFAULT '',
    tool_type           String DEFAULT '',
    tool_call_id        String DEFAULT '',
    tool_description    String DEFAULT '',
    tool_definitions    String DEFAULT '',

    -- Response
    finish_reasons      Array(String),

    -- Request params
    request_temperature Float64 DEFAULT 0,
    request_max_tokens  UInt64 DEFAULT 0,
    request_top_p       Float64 DEFAULT 0,

    -- Normalized messages (all provider formats resolved at extraction time)
    input_messages  Array(Tuple(role String, content String, tool_call_id String, tool_name String)) DEFAULT [],
    output_messages Array(Tuple(role String, content String, tool_call_id String, tool_name String)) DEFAULT [],

    -- System instructions as plain text array
    system_instructions Array(String) DEFAULT [],

    -- Tool call data (single invocation per span, kept as JSON)
    tool_call_arguments String DEFAULT '',
    tool_call_result    String DEFAULT '',

    -- Evaluation (OTel GenAI eval semconv — operation_name = 'evaluation')
    evaluation_name         String DEFAULT '',
    evaluation_score        Float64 DEFAULT 0,
    evaluation_label        String DEFAULT '',
    evaluation_explanation  String DEFAULT '',
    evaluated_span_id       String DEFAULT '',
    evaluated_trace_id      String DEFAULT '',

    -- Compaction tracking
    compaction_summary       String DEFAULT '',
    compaction_items_before  UInt32 DEFAULT 0,
    compaction_items_after   UInt32 DEFAULT 0,

    -- Weave media / lineage refs (native arrays for hasAny/arrayExists queries)
    content_refs        Array(String),
    artifact_refs       Array(String),
    object_refs         Array(String),

    -- Raw dumps (kept as backup for reprocessing, query via genai_span_attributes)
    attributes_dump     String DEFAULT '',
    events_dump         String DEFAULT '',
    resource_dump       String DEFAULT '',

    -- Auth
    wb_user_id          String DEFAULT '',

    -- Skip indexes for common filter patterns
    INDEX idx_span_id   span_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_trace_id  trace_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_parent    parent_span_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_op        operation_name TYPE set(20) GRANULARITY 4,
    INDEX idx_provider  provider_name TYPE set(20) GRANULARITY 4,
    INDEX idx_agent     agent_name TYPE set(100) GRANULARITY 4,
    INDEX idx_model     request_model TYPE set(100) GRANULARITY 4,
    INDEX idx_conv      conversation_id TYPE set(100) GRANULARITY 4,
    INDEX idx_tool      tool_name TYPE set(100) GRANULARITY 4,
    INDEX idx_eval_name evaluation_name TYPE set(100) GRANULARITY 4,
    INDEX idx_eval_label evaluation_label TYPE set(10) GRANULARITY 4
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, started_at, span_id)
SETTINGS min_bytes_for_wide_part=0, enable_block_number_column=1, enable_block_offset_column=1;


-- ---------------------------------------------------------------------------
-- 2. genai_span_attributes — EAV table for typed, indexable span attributes
--
-- Stores every non-semconv attribute as a typed row so we can filter, sort,
-- and aggregate on arbitrary user-supplied attributes without parsing JSON.
--
-- ORDER BY (project_id, attr_key, started_at, span_id):
--   - Prefix (project_id, attr_key) fast-paths "find spans where key X = Y"
--   - started_at enables partition pruning for time-range scans
--   - span_id gives uniqueness
-- ---------------------------------------------------------------------------
CREATE TABLE genai_span_attributes (
    project_id      String,
    started_at      DateTime64(6),
    span_id         String,
    attr_source     Enum8('span'=1, 'resource'=2) DEFAULT 'span',
    attr_key        String,

    value_type      Enum8('string'=1, 'int'=2, 'float'=3, 'bool'=4, 'json'=5),
    string_value    String DEFAULT '',
    int_value       Int64 DEFAULT 0,
    float_value     Float64 DEFAULT 0,
    bool_value      UInt8 DEFAULT 0,
    json_value      String DEFAULT '',

    created_at      DateTime64(3) DEFAULT now64(3),

    INDEX idx_span   span_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_sval   string_value TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_ival   int_value TYPE minmax GRANULARITY 4,
    INDEX idx_fval   float_value TYPE minmax GRANULARITY 4
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, attr_key, started_at, span_id)
SETTINGS min_bytes_for_wide_part=0;


-- ---------------------------------------------------------------------------
-- 3. genai_agents — per-agent aggregated stats (auto-populated by MV)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS genai_agents (
    project_id              String,
    agent_name              String,

    invocation_count        UInt64 DEFAULT 0,
    span_count              UInt64 DEFAULT 0,
    total_input_tokens      UInt64 DEFAULT 0,
    total_output_tokens     UInt64 DEFAULT 0,
    total_duration_ms       UInt64 DEFAULT 0,
    error_count             UInt64 DEFAULT 0,

    agent_description       SimpleAggregateFunction(max, String),
    agent_id                SimpleAggregateFunction(max, String),
    provider_name           SimpleAggregateFunction(max, String),
    system_instructions     SimpleAggregateFunction(max, String),

    first_seen              SimpleAggregateFunction(min, DateTime64(6)),
    last_seen               SimpleAggregateFunction(max, DateTime64(6)),

    llm_summary             SimpleAggregateFunction(max, String),
    llm_summary_updated_at  DateTime64(6) DEFAULT toDateTime64(0, 6),

    created_at              DateTime64(3) DEFAULT now64(3)
) ENGINE = SummingMergeTree((invocation_count, span_count, total_input_tokens, total_output_tokens, total_duration_ms, error_count))
ORDER BY (project_id, agent_name);


CREATE MATERIALIZED VIEW IF NOT EXISTS genai_agents_mv TO genai_agents AS
SELECT
    project_id,
    agent_name,
    toUInt64(operation_name = 'invoke_agent')               AS invocation_count,
    toUInt64(1)                                              AS span_count,
    toUInt64(input_tokens)                                   AS total_input_tokens,
    toUInt64(output_tokens)                                  AS total_output_tokens,
    toUInt64(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)) AS total_duration_ms,
    toUInt64(status_code = 'ERROR')                          AS error_count,
    agent_description,
    agent_id,
    provider_name,
    system_instructions,
    started_at                                               AS first_seen,
    started_at                                               AS last_seen,
    ''                                                       AS llm_summary,
    toDateTime64(0, 6)                                       AS llm_summary_updated_at
FROM genai_spans
WHERE agent_name != '';


-- ---------------------------------------------------------------------------
-- 4. genai_conversations — per-conversation aggregated stats (auto-populated by MV)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS genai_conversations (
    project_id              String,
    conversation_id         String,

    -- Aggregated stats (summed on merge)
    turn_count              UInt64 DEFAULT 0,
    span_count              UInt64 DEFAULT 0,
    total_input_tokens      UInt64 DEFAULT 0,
    total_output_tokens     UInt64 DEFAULT 0,
    total_duration_ms       UInt64 DEFAULT 0,
    error_count             UInt64 DEFAULT 0,

    -- Observed metadata (max keeps non-empty values over empty on merge)
    conversation_name       SimpleAggregateFunction(max, String),
    agent_name              SimpleAggregateFunction(max, String),
    provider_name           SimpleAggregateFunction(max, String),

    -- Time range
    first_seen              SimpleAggregateFunction(min, DateTime64(6)),
    last_seen               SimpleAggregateFunction(max, DateTime64(6)),

    created_at              DateTime64(3) DEFAULT now64(3)
) ENGINE = SummingMergeTree((turn_count, span_count, total_input_tokens, total_output_tokens, total_duration_ms, error_count))
ORDER BY (project_id, conversation_id);


CREATE MATERIALIZED VIEW IF NOT EXISTS genai_conversations_mv TO genai_conversations AS
SELECT
    project_id,
    conversation_id,
    toUInt64(operation_name = 'invoke_agent')               AS turn_count,
    toUInt64(1)                                              AS span_count,
    toUInt64(input_tokens)                                   AS total_input_tokens,
    toUInt64(output_tokens)                                  AS total_output_tokens,
    toUInt64(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)) AS total_duration_ms,
    toUInt64(status_code = 'ERROR')                          AS error_count,
    conversation_name,
    agent_name,
    provider_name,
    started_at                                               AS first_seen,
    started_at                                               AS last_seen
FROM genai_spans
WHERE conversation_id != '';


-- ---------------------------------------------------------------------------
-- 5. genai_scores — evaluation/signal results with typed outcome column
--
-- Purpose-built for signal analytics. Each row is one score from one
-- evaluator on one entity. outcome is Enum8 — countIf(outcome = 'pass')
-- is a 1-byte integer comparison, not a string scan.
--
-- Sort key (project_id, signal_name, scored_at, score_id) optimized for
-- "pass rate for signal X in the last 7 days" — a prefix scan on a
-- contiguous range.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS genai_scores (
    project_id          String,
    score_id            String,

    -- What was scored
    entity_type         String,
    entity_id           String,
    conversation_id     String DEFAULT '',

    -- The evaluation
    signal_name         String,
    outcome             Enum8('pass'=1, 'fail'=2, 'error'=3, 'unknown'=4),
    score_value         Float64 DEFAULT 0,
    label               String DEFAULT '',
    explanation         String DEFAULT '',

    -- Scorer metadata
    scorer_model        String DEFAULT '',
    scorer_prompt       String DEFAULT '',
    input_tokens        UInt64 DEFAULT 0,
    output_tokens       UInt64 DEFAULT 0,
    duration_ms         UInt64 DEFAULT 0,

    -- Time
    scored_at           DateTime64(3),
    created_at          DateTime64(3) DEFAULT now64(3),

    -- Auth
    wb_user_id          String DEFAULT '',

    -- Indexes
    INDEX idx_entity    entity_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_conv      conversation_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_signal    signal_name TYPE set(200) GRANULARITY 4,
    INDEX idx_outcome   outcome TYPE set(10) GRANULARITY 4
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(scored_at)
ORDER BY (project_id, signal_name, scored_at, score_id);


-- ---------------------------------------------------------------------------
-- 6. entity_annotations — generic EAV metadata on any entity
--
-- For display names, human labels, arbitrary tags. NOT for signal scores
-- (those go in genai_scores).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS entity_annotations (
    project_id          String,
    entity_type         String,
    entity_id           String,
    namespace           String,
    key                 String,

    string_value        String DEFAULT '',
    float_value         Float64 DEFAULT 0,
    int_value           Int64 DEFAULT 0,
    json_value          String DEFAULT '',
    value_type          Enum8('string'=1,'float'=2,'int'=3,'json'=4),

    source              String DEFAULT '',
    source_id           String DEFAULT '',
    updated_at          DateTime64(3) DEFAULT now64(3),

    deleted_at          DateTime64(3) DEFAULT toDateTime64(0, 3),

    INDEX idx_entity    entity_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_key       key TYPE set(200) GRANULARITY 4,
    INDEX idx_ns        namespace TYPE set(20) GRANULARITY 4,
    INDEX idx_sval      string_value TYPE bloom_filter(0.01) GRANULARITY 1
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (project_id, entity_type, entity_id, namespace, key)
SETTINGS do_not_merge_across_partitions_select_final = 1;


-- ---------------------------------------------------------------------------
-- 7. genai_message_search — per-message full-text search index
--
-- One row per unique (project_id, content_digest). Same message text across
-- repeated input_messages histories deduplicates via ReplacingMergeTree.
-- Populated at ingest time alongside genai_spans.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS genai_message_search (
    project_id          String,
    content_digest      String,

    -- Message identity
    conversation_id     String DEFAULT '',
    trace_id            String,
    span_id             String,
    role                String DEFAULT '',
    started_at          DateTime64(6),

    -- Full message text (searchable)
    content             String,

    -- Denormalized metadata for filtering within search results
    agent_name          String DEFAULT '',
    conversation_name   String DEFAULT '',
    wb_user_id          String DEFAULT '',
    provider_name       String DEFAULT '',
    request_model       String DEFAULT '',
    operation_name      String DEFAULT '',

    created_at          DateTime64(3) DEFAULT now64(3),

    -- Skip indexes for text search acceleration
    INDEX idx_content   content TYPE ngrambf_v1(3, 512, 2, 0) GRANULARITY 1,
    INDEX idx_agent     agent_name TYPE ngrambf_v1(3, 256, 2, 0) GRANULARITY 1,
    INDEX idx_conv_name conversation_name TYPE ngrambf_v1(3, 256, 2, 0) GRANULARITY 1,
    INDEX idx_role      role TYPE set(10) GRANULARITY 4,
    INDEX idx_conv_id   conversation_id TYPE set(100) GRANULARITY 4,
    INDEX idx_trace_id  trace_id TYPE bloom_filter GRANULARITY 1
) ENGINE = ReplacingMergeTree(created_at)
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, content_digest)
SETTINGS min_bytes_for_wide_part = 0;
