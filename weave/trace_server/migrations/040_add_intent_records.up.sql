-- One row per distilled intent occurrence, including its embedding and trace
-- provenance. ReplacingMergeTree gives idempotent, append-only upserts keyed on
-- (project_id, pipeline_version, id). The highest record_version wins, so a
-- retry or re-embed of the same occurrence collapses instead of duplicating.
CREATE TABLE IF NOT EXISTS intent_records
(
    project_id String,
    id String,                               -- deterministic hash of the occurrence, so retries collapse instead of duplicating
    signature_id FixedString(16),            -- 128-bit hash of the canonicalized signature, groups every occurrence of the same intent
    pipeline_version UInt32,                 -- recipe id, in ORDER BY so versions coexist during re-embed/backfill
    record_version UInt64,                   -- ReplacingMergeTree version, highest for a key wins

    category LowCardinality(String),         -- taxonomy label, mutable, deliberately excluded from identity
    signature String,
    embedding_model LowCardinality(String),
    embedding_dimensions UInt16 DEFAULT 1024,
    vector Array(Float32),                   -- searched by exact cosine distance, intentionally no ANN index

    source LowCardinality(String),
    source_id String DEFAULT '',
    trace_id String DEFAULT '',
    span_id String DEFAULT '',
    parent_span_id String DEFAULT '',
    conversation_id String DEFAULT '',
    turn_id String DEFAULT '',
    intent_ordinal UInt16 DEFAULT 0,         -- position among the intents extracted from a single turn
    user_id String DEFAULT '',               -- pseudonymous source subject, distinct from the writer

    intent_extracted_at DateTime64(6, 'UTC'),           -- partition key, set once at extraction, stable across retries
    inserted_at DateTime64(3, 'UTC') DEFAULT now64(3),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',   -- per-row retention override, default effectively never
    attributes Map(String, String),          -- free-form, not indexed or searchable

    INDEX idx_signature_id signature_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_span_id span_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(record_version)
PARTITION BY toYYYYMM(intent_extracted_at)
ORDER BY (project_id, pipeline_version, id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
