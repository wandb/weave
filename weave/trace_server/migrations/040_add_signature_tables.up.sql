-- One distilled user intent per row, associated with a turn. 1:many turn:signature relationship
CREATE TABLE IF NOT EXISTS intent_signatures
(
    project_id String,
    id UUID DEFAULT generateUUIDv7(),
    -- Digest of insights/configs/intent.json
    config_sha LowCardinality(String),

    -- Canonicalized before insert, lossy, use signature_display for exact judge wording.
    signature String,
    signature_display String DEFAULT '',
    category LowCardinality(String),
    -- ISO 639-1, or the ISO 639-2 'und' sentinel.
    language LowCardinality(String) DEFAULT 'und',
    sentiment LowCardinality(String) DEFAULT '',
    sentiment_rationale String DEFAULT '',
    sentiment_confidence Float32 DEFAULT -1,
    vector Array(Float32),

    -- Denormalized span data
    conversation_id String,
    turn_trace_id String,
    user_id String DEFAULT '',
    agent_name LowCardinality(String) DEFAULT '',
    duration_ms UInt32 DEFAULT 0,
    cost_usd Float64 DEFAULT 0,
    source_started_at DateTime64(6, 'UTC'),

    extracted_at DateTime64(6, 'UTC'),
    inserted_at DateTime64(6, 'UTC') MATERIALIZED now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_turn_trace_id turn_trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(source_started_at)
ORDER BY (project_id, toDate(source_started_at), id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;


-- One detected failure per row, associated with a turn. 1:many turn:signature relationship
CREATE TABLE IF NOT EXISTS failure_signatures
(
    project_id String,
    id UUID DEFAULT generateUUIDv7(),
    -- Digest of insights/configs/failure.json
    config_sha LowCardinality(String),

    -- Canonicalized before insert, lossy, use signature_display for exact judge wording.
    signature String,
    signature_display String DEFAULT '',
    -- Grounded prose explaining the claim, never embedded.
    failure_reason String DEFAULT '',
    category LowCardinality(String),
    severity LowCardinality(String) DEFAULT '',
    vector Array(Float32),

    -- Denormalized span data
    conversation_id String,
    -- The turn the failure was detected in, and the turn the row id anchors on.
    onset_turn_trace_id String,
    -- Turns the failure is attributed to, sorted, deduplicated, always contains the onset.
    turn_trace_ids Array(String),
    -- Spans the judge cited as evidence, resolved by the writer from message indices.
    evidence_span_ids Array(String) DEFAULT [],
    user_id String DEFAULT '',
    agent_name LowCardinality(String) DEFAULT '',
    -- Summed across turn_trace_ids, not additive across rows, two failures can share a turn.
    duration_ms UInt32 DEFAULT 0,
    cost_usd Float64 DEFAULT 0,
    source_started_at DateTime64(6, 'UTC'),

    extracted_at DateTime64(6, 'UTC'),
    inserted_at DateTime64(6, 'UTC') MATERIALIZED now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_turn_trace_ids turn_trace_ids TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(source_started_at)
ORDER BY (project_id, toDate(source_started_at), id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
