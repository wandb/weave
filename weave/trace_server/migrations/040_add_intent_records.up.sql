-- One row per distilled intent occurrence, including its embedding and complete
-- trace provenance. ReplacingMergeTree provides append-only logical updates
-- keyed on (project_id, pipeline_version, created_at, id). created_at is the
-- immutable occurrence time and sits in both the partition and dedup key, so
-- every rewrite (retry, tombstone, re-embed) must carry it forward unchanged;
-- a drifted created_at would land in another key/partition and never collapse.
CREATE TABLE IF NOT EXISTS intent_records
(
    -- Trusted tenancy and logical identity.
    project_id String,
    id String,
    pipeline_version UInt32,
    record_version UInt64,
    deleted Bool DEFAULT false,

    -- Intent classification. Add new top-level spaces with
    -- ALTER TABLE intent_records MODIFY COLUMN space ADD ENUM VALUES (...).
    space Enum8('intent' = 1, 'failure' = 2),
    category LowCardinality(String),
    status LowCardinality(String),

    -- Distilled signature and embedding.
    signature String,
    normalized_signature String,
    -- Raw 128-bit digest of (space, normalized_signature), not hexadecimal.
    signature_id FixedString(16),
    embedding_model LowCardinality(String),
    embedding_dimensions UInt16 DEFAULT 1024,
    vector Array(Float32),

    -- Source provenance.
    source LowCardinality(String),
    source_id String DEFAULT '',
    trace_id String DEFAULT '',
    span_id String DEFAULT '',
    parent_span_id String DEFAULT '',
    conversation_id String DEFAULT '',
    turn_id String DEFAULT '',
    intent_ordinal UInt16 DEFAULT 0,
    role LowCardinality(String) DEFAULT '',
    user_id String DEFAULT '',

    -- Occurrence time, insertion audit, retention, and cold metadata.
    created_at DateTime64(6, 'UTC'),
    inserted_at DateTime64(3, 'UTC') DEFAULT now64(3),
    inserted_by_user_id String,
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',
    attributes Map(String, String),

    INDEX idx_id id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_signature_id signature_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_span_id span_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(record_version)
PARTITION BY toYYYYMM(created_at)
ORDER BY (project_id, pipeline_version, created_at, id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
