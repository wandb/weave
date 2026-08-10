-- One distilled user intent per row: one turn, one claim, one embedding.
--
-- IDENTITY. id = hex(hash(project_id, conversation_id, trace_id,
--                         canonical_signature, toDate(source_started_at)))
--   The canonical signature is hashed directly. There is no stored
--   signature_id, so nothing can disagree with the text it came from.
--   toDate(source_started_at) is folded in because it is in the sorting key and
--   therefore in the replacement identity: a re-extraction whose snapshot
--   drifted across midnight must produce a visibly new id, not a silent
--   duplicate.
--
-- VERSION. inserted_at is the ReplacingMergeTree version. The writer supplies
--   nothing; the server stamps it, so there is one clock rather than one per
--   writer pod and a retry wins automatically. now64() is evaluated once per
--   insert block, so rows sharing an id inside one block tie and the writer
--   must deduplicate by id per batch.
--
-- LABELS. category and sentiment are validated by the writer against the
--   taxonomy files folded into config_sha256. The DDL encodes no label set and
--   carries no constraints: inserts are batched, so a CHECK or an Enum would
--   turn one bad candidate into a failed batch of 256. The writer drops the
--   candidate, counts it, and inserts the rest.
--
-- PIPELINE PROVENANCE. config_sha256 resolves to a checked-in config file that
--   names the prompt, taxonomy, context builder, judge, and embedding model.
--   Nothing about the pipeline is in the sorting key, so re-embedding produces
--   the same id and replaces in place. Two embedding generations coexist via a
--   shadow table and EXCHANGE TABLES, never in one table, which is what keeps
--   cosineDistance from ever seeing two dimensionalities.
CREATE TABLE IF NOT EXISTS intent_signatures
(
    project_id String,
    id String,
    config_sha256 LowCardinality(String),

    -- Canonical form, canonicalized before insert, so grouping by it is
    -- grouping by identity.
    signature String,
    category LowCardinality(String),
    -- ISO 639-1, or the ISO 639-2 'und' sentinel. Signatures are
    -- English-normalized, so this is the only record of the source language.
    language LowCardinality(String) DEFAULT 'und',
    -- The label the model emitted. No numeric encoding: averaging ordinal
    -- labels asserts distances the taxonomy does not define.
    sentiment LowCardinality(String) DEFAULT '',
    -- Exact cosine, intentionally no ANN index. Measured on this schema, HNSW
    -- cost 126-196x on inserts and 4.3-7.2x on reads.
    vector Array(Float32),

    conversation_id String DEFAULT '',
    -- The turn this intent came from, joinable to spans.trace_id. Weave defines
    -- one turn as one trace, so this is the turn key; there is no turn_id in
    -- the agent-spans world. Exactly one.
    trace_id String,
    -- Pseudonymous source subject, not the authenticated writer.
    user_id String DEFAULT '',
    -- The one denormalized facet; everything else joins `spans`.
    agent_name LowCardinality(String) DEFAULT '',
    -- The turn's own totals, copied from the agents API's total_duration_ms and
    -- total_cost_usd. Denormalized because they are sums over every span in the
    -- turn rather than a per-span lookup, and every ranked view needs them per
    -- row.
    duration_ms UInt32 DEFAULT 0,
    cost_usd Float64 DEFAULT 0,

    -- Snapshot of the source turn's start, taken at extraction and never
    -- re-read, so it is the analysis clock rather than the pipeline clock.
    source_started_at DateTime64(6, 'UTC'),
    -- The backfill sweep selects on this.
    extracted_at DateTime64(6, 'UTC'),
    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    -- Retention only. Retraction uses a lightweight DELETE, because TTL is
    -- asynchronous and a row awaiting its merge still answers reads.
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_signature signature TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(inserted_at)
-- Source month so retention and range reads follow user activity. Nothing about
-- the pipeline is here: PARTITION BY and ORDER BY cannot be altered on a
-- populated table, so they carry only what is certain.
PARTITION BY toYYYYMM(source_started_at)
-- Tenancy, time, identity. toDate(source_started_at) precedes id so a sub-month
-- read prunes granules; day rather than the raw timestamp keeps the replacement
-- identity as coarse as it can be while still pruning.
ORDER BY (project_id, toDate(source_started_at), id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
