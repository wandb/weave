-- Two tables for distilled conversation insights, split by grain: an intent is
-- one turn, a failure is one whole conversation. A single table would need a
-- lens discriminator that defaults every grain-specific column on the wrong
-- half of the rows, plus a cross-lens CHECK to police it.
--
-- They share 15 columns, identical in name and type, asserted by a test.

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
--   nothing: the server stamps it, so there is one clock rather than one per
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
-- PIPELINE PROVENANCE. config_sha256 is the digest of
--   weave/trace_server/insights/configs/intent.json, which today names the
--   taxonomy, the sentiment labels, and the embedding model. The prompt, judge,
--   and context builder join it when the writer lands. The digest resolves
--   every declared file reference, so adding one needs no schema change.
--   Nothing about the pipeline is in the sorting key, so re-embedding produces
--   the same id and replaces in place. Two embedding generations coexist via a
--   shadow table and EXCHANGE TABLES, never in one table, which is what keeps
--   cosineDistance from ever seeing two dimensionalities.
CREATE TABLE IF NOT EXISTS intent_signatures
(
    project_id String,
    id String,
    -- Digest of insights/configs/<space>.json (see insights/config.py).
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
    -- one turn as one trace, so this is the turn key. There is no turn_id in
    -- the agent-spans world. Exactly one.
    trace_id String,
    -- Pseudonymous source subject, not the authenticated writer.
    user_id String DEFAULT '',
    -- The one denormalized facet. Everything else joins `spans`.
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
-- read prunes granules. Day rather than the raw timestamp keeps the replacement
-- identity as coarse as it can be while still pruning.
ORDER BY (project_id, toDate(source_started_at), id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;


-- One detected failure per row: one conversation, one claim, one embedding, and
-- every turn the failure is attributed to.
--
-- IDENTITY. id = hex(hash(project_id, conversation_id, onset_trace_id,
--                         canonical_signature, toDate(source_started_at)))
--   onset_trace_id rather than trace_ids: a re-extraction that widens the
--   attributed span by one turn is the SAME failure and must replace it.
--
-- VERSION. inserted_at, as in intent_signatures. The writer supplies nothing.
--
-- GROUNDING, enforced by the writer and not the database. trace_ids is sorted,
--   deduplicated, non-empty, and contains onset_trace_id. These are writer
--   gates so one bad candidate is dropped and counted instead of failing its
--   256-row batch. A periodic off-path assertion query catches a writer bug:
--
--     SELECT count() FROM failure_signatures
--     WHERE project_id = {project_id:String}
--       AND (empty(trace_ids) OR NOT has(trace_ids, onset_trace_id))
--
--   Canonical ordering matters because trace_ids is compared for equality
--   during backfill reconciliation, and an unsorted array makes two identical
--   failures look different.
CREATE TABLE IF NOT EXISTS failure_signatures
(
    project_id String,
    id String,
    -- Digest of insights/configs/<space>.json (see insights/config.py).
    config_sha256 LowCardinality(String),

    -- The short canonical claim. This is what is embedded.
    signature String,
    -- Grounded prose explaining the claim. Never embedded, never in the id
    -- hash, freely regenerable, which is why a rephrased rationale does not
    -- move a cluster.
    failure_reason String DEFAULT '',
    category LowCardinality(String),
    severity LowCardinality(String) DEFAULT '',
    vector Array(Float32),

    conversation_id String,
    -- First turn where it went wrong. The single anchor for ranking and
    -- drilldown, and the only turn in the id hash.
    onset_trace_id String,
    -- Every turn the failure is attributed to, each joinable to spans.trace_id.
    -- Sorted and deduplicated by the writer so two identical failures compare
    -- equal during reconciliation.
    trace_ids Array(String),
    user_id String DEFAULT '',
    agent_name LowCardinality(String) DEFAULT '',
    -- Summed across trace_ids. Per-row only: two failures in one conversation
    -- can share a turn, so these are NOT additive across rows. A true total
    -- comes from the distinct union of trace_ids against `spans`.
    duration_ms UInt32 DEFAULT 0,
    cost_usd Float64 DEFAULT 0,

    -- Start of the attributed window.
    source_started_at DateTime64(6, 'UTC'),
    extracted_at DateTime64(6, 'UTC'),
    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_signature signature TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1,
    -- Serves has(trace_ids, {trace_id}), the drilldown from a turn to the
    -- failures touching it. Also covers onset_trace_id, always a member.
    INDEX idx_trace_ids trace_ids TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(source_started_at)
ORDER BY (project_id, toDate(source_started_at), id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

-- One row per turn, holding the derived context both judges need on the turns
-- that follow. Not a signature table: nothing here is embedded or clustered,
-- which is why it carries no vector, category, or signature, and why the drift
-- guard over the two signature tables deliberately does not cover it.
CREATE TABLE IF NOT EXISTS turn_context
(
    project_id String,
    conversation_id String,
    -- Position of the turn in its conversation. With conversation_id this is the
    -- turn identity, so there is no hashed id and no version column: the sorting
    -- key already names the row a re-judgment should replace.
    turn_index UInt16,
    -- The turn's trace, joinable to spans.trace_id. Weave defines one turn as one
    -- trace, so this is a second name for the same identity, carried for the
    -- drilldown from a trace back to its context.
    trace_id String,
    config_sha256 LowCardinality(String),

    -- One sentence describing the assistant response, from the failure judge.
    -- Written for every turn, including turns with no failure and no intent,
    -- which is the reason it cannot live on either signature table.
    assistant_summary String DEFAULT '',
    -- Constraints the user established, changed, or retracted on this turn, from
    -- the intent judge. Empty on most turns. The standing set handed to the
    -- failure judge is the accumulation of these, assembled at read time.
    constraints Array(String),

    source_started_at DateTime64(6, 'UTC'),
    extracted_at DateTime64(6, 'UTC'),
    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(source_started_at)
-- Ordered for the one read that runs on every judged turn: the prior N turns of a
-- single conversation. conversation_id sits in the sorting key rather than in a
-- bloom filter, so that read is a contiguous range instead of a scatter. No time
-- term, because this table is read by conversation rather than by window, and the
-- month partition is enough pruning for retention.
ORDER BY (project_id, conversation_id, turn_index)
TTL expire_at DELETE
-- These rows are small enough that index_granularity_bytes never binds, so the
-- default 8192-row granule would serve an 8-row answer. 1024 cuts that over-read
-- roughly 8x for an 8x larger primary index on a table measured at ~104 bytes/row.
SETTINGS min_bytes_for_wide_part = 0, index_granularity = 1024;
