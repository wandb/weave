-- Two tables for distilled conversation insights, split by grain: an intent is
-- one turn, a failure is one whole conversation. A single table would need a
-- kind discriminator that defaults every grain-specific column on the wrong
-- half of the rows, plus a CHECK across both halves to police it.
--
-- They share 17 columns, identical in name and type, asserted by a test.
--
-- READING EITHER SIGNATURE TABLE. Both are ReplacingMergeTree and no read here
-- uses FINAL, so a re-extraction leaves two physical rows until a merge and every
-- reader must collapse them itself. The canonical shape, cheaper than argMax over
-- a wide projection because it never materializes the 4 KB vector per group:
--
--   SELECT ... FROM intent_signatures
--   WHERE project_id = {project_id:String} AND ...
--   ORDER BY inserted_at DESC
--   LIMIT 1 BY project_id, toDate(source_started_at), id
--
-- An aggregate that cannot be expressed that way (avg, quantile, topK) must run
-- over a collapsed subquery, not over the raw rows, or a re-extracted row is
-- counted twice.
--
-- NO PER-TURN CONTEXT TABLE, deliberately. A judge assembles one turn's context
-- from these two tables plus `messages`, which measured 30 ms and 63k rows at 1M
-- turns against a judge completion of 1-3 s. A table denormalizing that per turn
-- measured 3.3x faster, but it holds nothing these three do not already hold, so
-- it is a read model addable by backfill whenever the read stops being 2% of the
-- pipeline's wall clock. Adding it later costs a migration and no data.

-- One distilled user intent per row: one turn, one claim, one embedding.
--
-- IDENTITY. id = hex(hash(project_id, conversation_id, trace_id,
--                         canonical_signature, toDate(source_started_at)))
--   The canonical signature is hashed directly, so no writer-supplied id can
--   disagree with the text it came from. `signature_id` below is a different
--   thing: MATERIALIZED, computed by ClickHouse, and used only to join clusters.
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
    -- grouping by identity. Canonicalization casefolds, so this is not the
    -- string to render.
    signature String,
    -- The judge's wording, verbatim. Never hashed, never embedded, never grouped:
    -- it exists because canonicalization is lossy and the original casing cannot
    -- be recovered later without paying for a re-judge.
    signature_display String DEFAULT '',
    -- The cluster-table join key, computed by ClickHouse rather than supplied, so
    -- the writer cannot disagree with the function the join uses. Stored and
    -- indexed because the product read is "every occurrence in this cluster",
    -- which arrives holding hashes: without a column, that filter is
    -- sipHash128(signature) evaluated per row over the whole window with no
    -- pruning possible.
    signature_id FixedString(16) MATERIALIZED sipHash128(signature),
    category LowCardinality(String),
    -- ISO 639-1, or the ISO 639-2 'und' sentinel. Signatures are
    -- English-normalized, so this is the only record of the source language.
    language LowCardinality(String) DEFAULT 'und',
    -- The label the model emitted. No numeric encoding: averaging ordinal
    -- labels asserts distances the taxonomy does not define.
    sentiment LowCardinality(String) DEFAULT '',
    -- Why the judge picked that label, in its words, and how sure it was. Never
    -- embedded and never in the id hash, so a reworded rationale keeps the row.
    sentiment_rationale String DEFAULT '',
    -- -1 rather than 0, which would collide "not reported" with "certainly not".
    sentiment_confidence Float32 DEFAULT -1,
    -- Exact cosine, intentionally no ANN index: measured on this schema, HNSW
    -- cost 126-196x on inserts, and an exact scan is inside budget at this
    -- volume. The earlier claim that HNSW also cost 4.3-7.2x on reads is not
    -- cited here, because a build that loses to a brute-force scan is more
    -- likely to have gone unused than to be that slow.
    vector Array(Float32),

    -- Required, not defaulted: an empty value would bucket every rollup under ''.
    conversation_id String,
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

    INDEX idx_signature_id signature_id TYPE bloom_filter(0.01) GRANULARITY 1,
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
    -- The judge's wording, verbatim. See intent_signatures.signature_display.
    signature_display String DEFAULT '',
    -- See intent_signatures.signature_id.
    signature_id FixedString(16) MATERIALIZED sipHash128(signature),
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
