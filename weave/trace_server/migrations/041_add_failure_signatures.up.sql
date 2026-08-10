-- One detected failure per row: one conversation, one claim, one embedding, and
-- every turn the failure is attributed to.
--
-- Split from intent_signatures rather than sharing a table with a lens column,
-- because the grain differs: an intent is one turn, a failure is a whole
-- conversation. A discriminator column would have defaulted every grain-specific
-- column on the wrong half of the rows.
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
--   256-row batch; a periodic off-path assertion query catches a writer bug:
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
    config_sha256 LowCardinality(String),

    -- The short canonical claim; this is what is embedded.
    signature String,
    -- Grounded prose explaining the claim. Never embedded, never in the id
    -- hash, freely regenerable, which is why a rephrased rationale does not
    -- move a cluster.
    failure_reason String DEFAULT '',
    category LowCardinality(String),
    severity LowCardinality(String) DEFAULT '',
    vector Array(Float32),

    conversation_id String,
    -- First turn where it went wrong; the single anchor for ranking and
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
