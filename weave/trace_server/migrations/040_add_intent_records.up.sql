-- One row per distilled intent occurrence, including its embedding and trace
-- provenance. ReplacingMergeTree gives idempotent, append-only upserts keyed on
-- the full sorting key. The highest record_version wins, so a retry or re-embed
-- of the same occurrence collapses instead of duplicating.
CREATE TABLE IF NOT EXISTS intent_records
(
    project_id String,
    -- Deterministic hash of (conversation_id, turn_index, lens, signature_id,
    -- toDate(source_started_at)): every sorting-key term the writer controls. A
    -- re-extraction that reorders or repeats a signature therefore collapses
    -- instead of landing a second row under a supposedly unique id.
    id String,
    -- 128-bit hash of the canonicalized signature AND the lens, so it groups
    -- every occurrence of the same intent while keeping the two lenses distinct.
    -- The same text as an intent and as a failure are different objects, and a
    -- shared id would let one lens inflate the other's counts. Downstream
    -- cluster tables rely on this to key on signature_id with no lens column.
    signature_id FixedString(16),
    -- Analysis lens, 'intent' or 'failure'. In the sorting key so a single-lens
    -- read prunes, which costs nothing because it is already folded into id and
    -- signature_id. No DEFAULT: an omitted lens matches no run, which is louder
    -- than silently claiming to be an intent.
    lens LowCardinality(String),
    pipeline_version UInt32,                 -- recipe id, in ORDER BY so versions coexist during re-embed/backfill
    record_version UInt64,                   -- ReplacingMergeTree version, highest for a key wins

    category String,                         -- mutable taxonomy label, excluded from identity, plain String because generated categories can be high-cardinality
    signature String,
    -- ISO 639-1 code of the source turn's prose, or the ISO 639-2 'und'
    -- sentinel when indeterminate, which is also the DEFAULT so unknown has one
    -- value. Signatures are English-normalized, so this is the only record of
    -- the original and the only way to see judge quality vary by language.
    language LowCardinality(String) DEFAULT 'und',

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

    trace_id String DEFAULT '',
    span_id String DEFAULT '',               -- root span of the source turn, the pointer back into spans
    conversation_id String DEFAULT '',
    turn_index UInt16 DEFAULT 0,             -- position of the source turn in its conversation. (conversation_id, turn_index) is the turn identity
    user_id String DEFAULT '',               -- pseudonymous source subject, distinct from the writer

    -- Execution context of the source turn, denormalized at extraction like
    -- source_started_at. A turn's rows all repeat these, lens='failure' included.
    agent_name LowCardinality(String) DEFAULT '',
    agent_version String DEFAULT '',          -- free-form version label, so plain String rather than a bounded vocabulary
    provider LowCardinality(String) DEFAULT '',
    request_model LowCardinality(String) DEFAULT '', -- model the source turn called, distinct from judge_model and embedding_model
    surface LowCardinality(String) DEFAULT '',
    status_code Enum8('UNSET' = 0, 'OK' = 1, 'ERROR' = 2) DEFAULT 'UNSET', -- same vocabulary as spans.status_code, so the two join without a cast
    turn_duration_ms UInt32 DEFAULT 0,
    turn_cost_usd Float64 DEFAULT 0,
    turn_summary String DEFAULT '',           -- describes the assistant response, so it repeats across a turn's rows

    -- Denormalized SNAPSHOT of the source turn's start time, captured at
    -- extraction and never re-read from the source. This is the analysis clock.
    source_started_at DateTime64(6, 'UTC'),
    intent_extracted_at DateTime64(6, 'UTC'),           -- pipeline clock, set once at extraction, stable across retries
    inserted_at DateTime64(3, 'UTC') DEFAULT now64(3),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',   -- per-row retention override, default effectively never

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
-- lens precedes the time term so a single-lens read prunes to one contiguous
-- block. toDate(source_started_at) precedes id so a sub-month read prunes
-- granules: without it, source time lives only in the partition key and any
-- window narrower than a month still scans the whole month.
--
-- Every term here is part of the replacement identity, so the id hash folds
-- them all in (see id above). Day rather than the raw timestamp keeps the
-- identity as coarse as it can be while still pruning: a microsecond key would
-- make every sub-second snapshot difference a distinct row.
ORDER BY (project_id, pipeline_version, lens, toDate(source_started_at), id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
