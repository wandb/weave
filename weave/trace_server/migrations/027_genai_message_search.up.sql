-- =============================================================================
-- GenAI message search: per-message full-text search index
--
-- Stores one row per unique (project_id, content_digest) — same message text
-- across repeated input_messages histories deduplicates via ReplacingMergeTree.
--
-- Populated at ingest time in genai_otel_export alongside genai_spans.
-- Search queries use positionCaseInsensitive() accelerated by ngrambf skip
-- indexes on the content and metadata columns.
-- =============================================================================

CREATE TABLE IF NOT EXISTS genai_message_search (
    project_id          String,
    content_digest      String,

    -- Message identity
    conversation_id     String DEFAULT '',
    trace_id            String,
    span_id             String,
    role                LowCardinality(String) DEFAULT '',
    started_at          DateTime64(6),

    -- Full message text (searchable)
    content             String,

    -- Denormalized metadata for filtering within search results
    agent_name          String DEFAULT '',
    conversation_name   String DEFAULT '',
    wb_user_id          String DEFAULT '',
    provider_name       LowCardinality(String) DEFAULT '',
    request_model       String DEFAULT '',
    operation_name      LowCardinality(String) DEFAULT '',

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
