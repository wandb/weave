-- One distilled user intent per row, associated with a turn. 1:many turn:signature relationship
CREATE TABLE IF NOT EXISTS intent_signatures
(
    project_id String,
    -- Writer-minted uuidv7, so only a retry reusing this id collapses in the merge.
    id UUID DEFAULT generateUUIDv7(),
    -- Digest of insights/configs/intent.yaml
    config_sha LowCardinality(String),

    -- Canonicalized before insert, so it is lossy against the judge's exact wording.
    signature String,
    category String,
    -- ISO 639-1 two-letter ('en', 'es'), or the ISO 639-2 'und' sentinel.
    language LowCardinality(String) DEFAULT 'und',
    sentiment LowCardinality(String) DEFAULT 'neutral',
    sentiment_rationale String DEFAULT '',
    vector Array(Float32),

    -- Denormalized span data
    conversation_id String,
    trace_id String,
    user_id String DEFAULT '',
    agent_name String DEFAULT '',
    -- Whole-turn values copied onto every fan-out row, so summing them overcounts.
    turn_duration_ms UInt32 DEFAULT 0,
    turn_cost_usd Float64 DEFAULT 0,
    trace_started_at DateTime64(6, 'UTC'),

    extracted_at DateTime64(6, 'UTC'),
    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(trace_started_at)
ORDER BY (project_id, toDate(trace_started_at), id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;


-- One detected failure per row, associated with a turn. 1:many turn:signature relationship
CREATE TABLE IF NOT EXISTS failure_signatures
(
    project_id String,
    -- Writer-minted uuidv7, so only a retry reusing this id collapses in the merge.
    id UUID DEFAULT generateUUIDv7(),
    -- Digest of insights/configs/failure.yaml
    config_sha LowCardinality(String),

    -- Canonicalized before insert, so it is lossy against the judge's exact wording.
    signature String,
    -- Grounded prose explaining the claim, never embedded.
    failure_reason String DEFAULT '',
    category String,
    -- '' means no usable severity came back from the judge, never the 'info' label.
    severity LowCardinality(String) DEFAULT '',
    vector Array(Float32),

    -- Denormalized span data
    conversation_id String,
    -- The turn the failure was detected in.
    current_trace_id String,
    -- Turns the failure is attributed to, sorted, deduplicated, always contains the current turn.
    affected_trace_ids Array(String),
    -- Spans the judge cited as evidence, resolved by the writer from message indices.
    evidence_span_ids Array(String) DEFAULT [],
    user_id String DEFAULT '',
    agent_name String DEFAULT '',
    -- Summed across affected_trace_ids, not additive across rows, two failures can share a turn.
    turn_duration_ms UInt32 DEFAULT 0,
    turn_cost_usd Float64 DEFAULT 0,
    trace_started_at DateTime64(6, 'UTC'),

    extracted_at DateTime64(6, 'UTC'),
    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_affected_trace_ids affected_trace_ids TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(trace_started_at)
ORDER BY (project_id, toDate(trace_started_at), id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
