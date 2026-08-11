-- Two tables for distilled conversation insights, split by grain: an intent is
-- one turn, a failure is one whole conversation. One table would need a kind
-- discriminator that defaults every grain-specific column on the wrong half of
-- the rows, plus a CHECK across both halves to police it. The columns they do
-- share are asserted identical in name and type by a test.
--
-- READING EITHER TABLE. No read here uses FINAL, so a re-extraction leaves two
-- physical rows until a merge and every reader collapses them itself. This shape
-- is cheaper than argMax over a wide projection, which materializes the 4 KB
-- vector once per group:
--
--   SELECT ... FROM intent_signatures
--   WHERE project_id = {project_id:String} AND ...
--   ORDER BY inserted_at DESC
--   LIMIT 1 BY project_id, toDate(source_started_at), id
--
-- An aggregate that cannot be spelled that way (avg, quantile, topK) must run
-- over a collapsed subquery, or a re-extracted row is counted twice.
--
-- A judge's per-turn context is assembled from these two tables plus `messages`.
-- A table denormalizing it per turn measured faster but holds nothing the three
-- already hold, so it is a read model addable later by backfill rather than a
-- schema decision that has to be made now.

-- One distilled user intent per row: one turn, one claim, one embedding.
--
-- IDENTITY. id = hex(hash(project_id, conversation_id, trace_id,
--                         canonical_signature, toDate(source_started_at)))
--   The signature is hashed directly, so no writer-supplied id can disagree with
--   the text it came from. toDate(source_started_at) is folded in because it is
--   in the sorting key and therefore in the replacement identity: a re-extraction
--   whose snapshot drifted across midnight must produce a visibly new id rather
--   than a silent duplicate.
--
-- VERSION. inserted_at, stamped by the server so there is one clock rather than
--   one per writer pod and a retry wins automatically. now64() is evaluated once
--   per insert block, so rows sharing an id inside one block tie, and the writer
--   must deduplicate by id per batch.
--
-- LABELS. category and sentiment are validated by the writer against the taxonomy
--   files folded into config_sha256. No Enum and no CHECK: inserts are batched, so
--   either would turn one bad candidate into a failed batch of 256. The writer
--   drops the candidate, counts it, and inserts the rest.
--
-- PROVENANCE. config_sha256 digests insights/configs/intent.json with every
--   declared file reference resolved to its own digest, so adding a reference
--   needs no schema change. Nothing about the pipeline is in the sorting key, so
--   re-embedding produces the same id and replaces in place.
CREATE TABLE IF NOT EXISTS intent_signatures
(
    project_id String,
    id String,
    -- Digest of insights/configs/<space>.json (see insights/config.py).
    config_sha256 LowCardinality(String),

    -- Canonicalized before insert, so grouping by it is grouping by identity.
    -- Canonicalization casefolds and is lossy, so `signature` is never the string
    -- to render and `signature_display` holds the judge's wording verbatim.
    signature String,
    signature_display String DEFAULT '',
    -- The cluster-table join key, MATERIALIZED so the writer cannot disagree with
    -- the function the join uses. Stored and indexed because "every occurrence in
    -- this cluster" arrives holding hashes, which without a column prunes nothing.
    signature_id FixedString(16) MATERIALIZED sipHash128(signature),
    category LowCardinality(String),
    -- ISO 639-1, or the ISO 639-2 'und' sentinel. Signatures are
    -- English-normalized, so this is the only record of the source language.
    language LowCardinality(String) DEFAULT 'und',
    -- The label the model emitted. No numeric encoding: averaging ordinal labels
    -- asserts distances the taxonomy does not define.
    sentiment LowCardinality(String) DEFAULT '',
    -- Never embedded and never in the id hash, so a reworded rationale keeps the row.
    sentiment_rationale String DEFAULT '',
    -- -1 rather than 0, which would collide "not reported" with "certainly not".
    sentiment_confidence Float32 DEFAULT -1,
    -- Exact cosine, no ANN index: measured on this schema, HNSW cost 126-196x on
    -- inserts, and an exact scan is inside budget at this volume.
    vector Array(Float32),

    -- Required, not defaulted: an empty value would bucket every rollup under ''.
    conversation_id String,
    -- The turn this intent came from, joinable to spans.trace_id. Weave defines
    -- one turn as one trace, so this is the turn key. There is no turn_id in the
    -- agent-spans world. Exactly one.
    trace_id String,
    -- Pseudonymous source subject, not the authenticated writer.
    user_id String DEFAULT '',
    -- The three denormalized facets, so a ranked view needs no join: the agent,
    -- and the turn's own totals from the agents API, which are sums over every
    -- span in the turn rather than a per-span lookup. Everything else joins `spans`.
    agent_name LowCardinality(String) DEFAULT '',
    duration_ms UInt32 DEFAULT 0,
    cost_usd Float64 DEFAULT 0,

    -- Snapshot of the source turn's start, taken at extraction and never re-read,
    -- so it is the analysis clock rather than the pipeline clock.
    source_started_at DateTime64(6, 'UTC'),
    -- The pipeline clock, for reconciling a backfill against a live pass.
    -- Deliberately unindexed: a sweep over it scans the partition, which is what
    -- a backfill already does.
    extracted_at DateTime64(6, 'UTC'),
    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    -- Retention only. Retraction uses a lightweight DELETE, because TTL is
    -- asynchronous and a row awaiting its merge still answers reads.
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_signature_id signature_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(inserted_at)
-- Source month so retention and range reads follow user activity. PARTITION BY
-- and ORDER BY cannot be altered on a populated table, so they carry only what is
-- certain: tenancy, time, identity, and nothing about the pipeline.
PARTITION BY toYYYYMM(source_started_at)
-- toDate(source_started_at) precedes id so a sub-month read prunes granules. Day
-- rather than the raw timestamp keeps the replacement identity as coarse as it can
-- be while still pruning.
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
-- VERSION, LABELS, and PROVENANCE as in intent_signatures.
--
-- GROUNDING, a writer gate rather than a CHECK, for the batching reason above.
--   trace_ids is sorted, deduplicated, non-empty, and contains onset_trace_id.
--   Sorting matters because trace_ids is compared for equality during backfill
--   reconciliation, so an unsorted array makes two identical failures differ. An
--   off-path query catches a writer bug and must find nothing:
--
--     SELECT count() FROM failure_signatures
--     WHERE project_id = {project_id:String}
--       AND (empty(trace_ids) OR NOT has(trace_ids, onset_trace_id))
CREATE TABLE IF NOT EXISTS failure_signatures
(
    project_id String,
    id String,
    -- Digest of insights/configs/<space>.json (see insights/config.py).
    config_sha256 LowCardinality(String),

    -- The short canonical claim, and the judge's verbatim wording. See
    -- intent_signatures.signature.
    signature String,
    signature_display String DEFAULT '',
    -- See intent_signatures.signature_id.
    signature_id FixedString(16) MATERIALIZED sipHash128(signature),
    -- Grounded prose explaining the claim. Never embedded, never in the id hash,
    -- freely regenerable, which is why a rephrased rationale does not move a cluster.
    failure_reason String DEFAULT '',
    category LowCardinality(String),
    severity LowCardinality(String) DEFAULT '',
    vector Array(Float32),

    conversation_id String,
    -- First turn where it went wrong. The single anchor for ranking and
    -- drilldown, and the only turn in the id hash.
    onset_trace_id String,
    -- Every turn the failure is attributed to, each joinable to spans.trace_id.
    trace_ids Array(String),
    user_id String DEFAULT '',
    agent_name LowCardinality(String) DEFAULT '',
    -- Summed across trace_ids. Per-row only: two failures in one conversation can
    -- share a turn, so these are NOT additive across rows. A true total comes from
    -- the distinct union of trace_ids against `spans`.
    duration_ms UInt32 DEFAULT 0,
    cost_usd Float64 DEFAULT 0,

    -- Start of the attributed window.
    source_started_at DateTime64(6, 'UTC'),
    extracted_at DateTime64(6, 'UTC'),
    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_signature_id signature_id TYPE bloom_filter(0.01) GRANULARITY 1,
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
