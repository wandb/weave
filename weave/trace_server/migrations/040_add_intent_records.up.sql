-- One row per distilled intent occurrence, including its embedding and trace
-- provenance. ReplacingMergeTree gives idempotent, append-only upserts keyed on
-- (project_id, pipeline_version, id). The highest record_version wins, so a
-- retry or re-embed of the same occurrence collapses instead of duplicating.
CREATE TABLE IF NOT EXISTS intent_records
(
    project_id String,
    -- Deterministic hash of the occurrence, so retries collapse instead of
    -- duplicating. It MUST fold in toDate(source_started_at), because that
    -- expression is part of the sorting key and therefore part of the
    -- ReplacingMergeTree identity. If it did not, a re-extraction whose snapshot
    -- drifted across midnight would land a second row under an id the reader
    -- believes is unique. Folding it in makes a drifted snapshot a visibly new
    -- id instead of a silent duplicate.
    id String,
    intent_ordinal UInt16 DEFAULT 0,         -- position among intents extracted from a single turn, folded into the id hash
    -- 128-bit hash of the canonicalized signature AND the lens, so it groups
    -- every occurrence of the same intent while keeping the two lenses distinct.
    -- The same text as an intent and as a failure are different objects, and a
    -- shared id would let one lens inflate the other's counts. Downstream
    -- cluster tables rely on this to key on signature_id with no lens column.
    signature_id FixedString(16),
    -- Analysis lens, 'intent' or 'failure', already folded into the id and
    -- signature_id hashes so it stays out of ORDER BY. Deliberately has no
    -- DEFAULT: it is a discriminator, the rollup fold filters on it, and a row
    -- whose column disagrees with its own hashes is undetectable. An omitted
    -- lens reads back empty and matches no run, which is louder than silently
    -- claiming to be an intent.
    lens LowCardinality(String),
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

    -- Judged sentiment of the source turn. sentiment_score is an ALIAS so the
    -- ordinal scale has one home: rescoring is a migration, not a row rewrite.
    sentiment LowCardinality(String) DEFAULT '',
    sentiment_confidence Float32 DEFAULT 0,
    sentiment_score Float32 ALIAS transform(sentiment, ['frustrated', 'dissatisfied', 'neutral', 'satisfied', 'delighted'], [-1., -0.5, 0., 0.5, 1.], 0.),

    embedding_model LowCardinality(String),
    vector Array(Float32),                   -- searched by exact cosine distance, intentionally no ANN index. length(vector) is the dimensionality

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

    -- Execution context of the source turn, denormalized at extraction like
    -- source_started_at. A turn's rows all repeat these, lens='failure' included.
    agent_name LowCardinality(String) DEFAULT '',
    agent_version String DEFAULT '',          -- free-form version label, so plain String rather than a bounded vocabulary
    provider LowCardinality(String) DEFAULT '',
    request_model LowCardinality(String) DEFAULT '', -- model the source turn called, distinct from judge_model and embedding_model
    surface LowCardinality(String) DEFAULT '',
    status_code LowCardinality(String) DEFAULT '', -- String, not numeric: sources report both HTTP codes and symbolic names
    turn_duration_ms UInt32 DEFAULT 0,
    turn_cost_usd Float64 DEFAULT 0,
    turn_summary String DEFAULT '',           -- describes the assistant response, so it repeats across a turn's rows

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
-- toDate(source_started_at) precedes id so a sub-month read prunes granules.
-- Without it, source time lives only in the partition key and any window
-- narrower than a month still scans the whole month.
--
-- This expression is part of the replacement identity, so the id hash must fold
-- it in (see id above). Day rather than the raw timestamp keeps the identity as
-- coarse as it can be while still pruning: a microsecond key would make every
-- sub-second snapshot difference a distinct row.
ORDER BY (project_id, pipeline_version, toDate(source_started_at), id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
