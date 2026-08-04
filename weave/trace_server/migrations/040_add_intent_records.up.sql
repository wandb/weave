-- One row per distilled intent occurrence, including its embedding and trace
-- provenance. ReplacingMergeTree gives idempotent, append-only upserts keyed on
-- (project_id, pipeline_version, id). The highest record_version wins, so a
-- retry or re-embed of the same occurrence collapses instead of duplicating.
CREATE TABLE IF NOT EXISTS intent_records
(
    project_id String,
    id String,                               -- deterministic hash of the occurrence, so retries collapse instead of duplicating
    intent_ordinal UInt16 DEFAULT 0,         -- position among intents extracted from a single turn, folded into the id hash
    signature_id FixedString(16),            -- 128-bit hash of the canonicalized signature, groups every occurrence of the same intent
    space LowCardinality(String) DEFAULT 'intent', -- analysis lens, 'intent' or 'failure', already folded into the id hash so it stays out of ORDER BY
    pipeline_version UInt32,                 -- recipe id, in ORDER BY so versions coexist during re-embed/backfill
    record_version UInt64,                   -- ReplacingMergeTree version, highest for a key wins

    category String,                         -- mutable taxonomy label, excluded from identity, plain String because generated categories can be high-cardinality
    signature String,
    -- Judge decomposition of the signature. action/outcome/operation_mode are
    -- bounded vocabularies. object is a free-text noun phrase, so plain String.
    action LowCardinality(String) DEFAULT '',
    object String DEFAULT '',
    outcome LowCardinality(String) DEFAULT '',
    operation_mode LowCardinality(String) DEFAULT '',

    embedding_model LowCardinality(String),
    embedding_dimensions UInt16 DEFAULT 1024,
    vector Array(Float32),                   -- searched by exact cosine distance, intentionally no ANN index

    judge_model LowCardinality(String) DEFAULT '',
    prompt_version LowCardinality(String) DEFAULT '',
    -- Lowercase hex. pipeline_version is a 32-bit truncation of this digest and
    -- there is no recipe registry table, so the full digest is the audit trail.
    pipeline_recipe_sha256 String DEFAULT '',

    source LowCardinality(String),
    insights_type LowCardinality(String) DEFAULT 'turn', -- grain of analyzed unit: 'turn' or 'conversation'
    source_id String DEFAULT '',             -- id within the source system, hashed into id. Turn identity is (conversation_id, turn_index)
    trace_id String DEFAULT '',
    span_id String DEFAULT '',
    parent_span_id String DEFAULT '',
    conversation_id String DEFAULT '',
    turn_index UInt16 DEFAULT 0,             -- position of the source turn in its conversation, numeric so ranges and ordering work
    user_id String DEFAULT '',               -- pseudonymous source subject, distinct from the writer

    -- Clustering assignment for the run named by cluster_run_id. An empty
    -- cluster_run_id means never clustered. cluster_id -1 is the HDBSCAN noise label.
    cluster_run_id String DEFAULT '',
    cluster_id Int32 DEFAULT -1,
    cluster_label String DEFAULT '',         -- generated per cluster, plain String for the same reason as category
    cluster_confidence Float32 DEFAULT 0,

    -- Denormalized SNAPSHOT of the source turn's start time, captured at
    -- extraction and never re-read from the source. This is the analysis clock.
    source_started_at DateTime64(6, 'UTC'),
    intent_extracted_at DateTime64(6, 'UTC'),           -- pipeline clock, set once at extraction, stable across retries
    inserted_at DateTime64(3, 'UTC') DEFAULT now64(3),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',   -- per-row retention override, default effectively never
    attributes Map(String, String),          -- free-form, not indexed or searchable

    INDEX idx_signature_id signature_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_span_id span_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(record_version)
-- Partition on source time, not extraction time, so retention and time-range
-- reads follow user activity. A backfill spanning >100 months needs a raised
-- max_partitions_per_insert_block.
PARTITION BY toYYYYMM(source_started_at)
ORDER BY (project_id, pipeline_version, id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
