CREATE TABLE IF NOT EXISTS message_content (
    project_id String,
    content_digest FixedString(16),
    content String,
    expire_at DateTime,
    CONSTRAINT explicit_expiry CHECK expire_at > toDateTime(0),
    INDEX idx_content_words content TYPE text(tokenizer = splitByNonAlpha)
) ENGINE = ReplacingMergeTree(expire_at)
ORDER BY (project_id, content_digest)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

CREATE TABLE IF NOT EXISTS message_occurrences (
    project_id String,
    content_digest FixedString(16),
    trace_id String,
    span_id String,
    parent_span_id String DEFAULT '',
    conversation_id String DEFAULT '',
    conversation_name String DEFAULT '',
    agent_name String DEFAULT '',
    agent_version String DEFAULT '',
    provider_name String DEFAULT '',
    request_model String DEFAULT '',
    operation_name String DEFAULT '',
    role String DEFAULT '',
    started_at DateTime64(6),
    wb_user_id String DEFAULT '',
    created_at DateTime64(3),
    expire_at DateTime,
    CONSTRAINT explicit_source_version CHECK created_at > toDateTime64(0, 3),
    CONSTRAINT explicit_expiry CHECK expire_at > toDateTime(0),
    INDEX idx_digest content_digest TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_span_id span_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conv_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1
) ENGINE = ReplacingMergeTree(created_at)
PARTITION BY toYYYYMM(started_at)
PRIMARY KEY (project_id, started_at)
ORDER BY (project_id, started_at, span_id, trace_id, role, content_digest)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

CREATE MATERIALIZED VIEW IF NOT EXISTS message_content_mv TO message_content AS
SELECT project_id, murmurHash3_128(m.2) AS content_digest,
       m.2 AS content, expire_at
FROM spans
ARRAY JOIN arrayConcat(
    arrayMap(m -> (m.1, m.2), arrayConcat(input_messages, output_messages)),
    arrayMap(s -> ('system', s), system_instructions),
    [('tool_call', tool_call_arguments), ('tool_result', tool_call_result)]
) AS m
WHERE m.2 != '';

CREATE MATERIALIZED VIEW IF NOT EXISTS message_occurrences_mv TO message_occurrences AS
SELECT project_id, murmurHash3_128(m.2) AS content_digest,
       trace_id, span_id, parent_span_id,
       conversation_id, conversation_name, agent_name, agent_version,
       provider_name, request_model, operation_name, m.1 AS role, started_at,
       wb_user_id, created_at, expire_at
FROM spans
ARRAY JOIN arrayConcat(
    arrayMap(m -> (m.1, m.2), arrayConcat(input_messages, output_messages)),
    arrayMap(s -> ('system', s), system_instructions),
    [('tool_call', tool_call_arguments), ('tool_result', tool_call_result)]
) AS m
WHERE m.2 != '';
