-- Two tables for distilled conversation insights, split by grain: an intent is one
-- turn, a failure is one whole conversation. One table would need a kind
-- discriminator that defaults every grain-specific column on the wrong half of the
-- rows. The columns they share are asserted identical in name and type by a test.
--
-- Both are ReplacingMergeTree on inserted_at, which collapses exactly one thing: a
-- writer retrying the same row id. Re-extracting a turn is a new row.

-- One distilled user intent per row: one turn, one claim, one embedding.
CREATE TABLE IF NOT EXISTS intent_signatures
(
    project_id String,
    -- Minted by the writer before its first attempt so a retry carries the same id
    -- and collapses. Defaulted here only so a row can never land without one.
    id UUID DEFAULT generateUUIDv7(),
    -- Digest of insights/configs/<space>.json (see insights/config.py).
    config_sha256 LowCardinality(String),

    -- Canonicalized before insert, so grouping by it is grouping by identity.
    -- Canonicalization casefolds and is lossy, so this is never the string to
    -- render: signature_display holds the judge's wording verbatim.
    signature String,
    signature_display String DEFAULT '',
    category LowCardinality(String),
    -- ISO 639-1, or the ISO 639-2 'und' sentinel. Signatures are
    -- English-normalized, so this is the only record of the source language.
    language LowCardinality(String) DEFAULT 'und',
    -- The label the model emitted. No numeric encoding: averaging ordinal labels
    -- asserts distances the taxonomy does not define.
    sentiment LowCardinality(String) DEFAULT '',
    sentiment_rationale String DEFAULT '',
    -- -1 rather than 0, which would collide "not reported" with "certainly not".
    sentiment_confidence Float32 DEFAULT -1,
    -- Exact cosine, no ANN index: measured on this schema, HNSW cost 126-196x on
    -- inserts, and an exact scan is inside budget at this volume.
    vector Array(Float32),

    -- Required, not defaulted: an empty value would bucket every rollup under ''.
    conversation_id String,
    -- The turn this intent came from, joinable to spans.trace_id. Weave defines one
    -- turn as one trace, so this is the turn key. There is no turn_id here.
    trace_id String,
    -- Pseudonymous source subject, not the authenticated writer.
    user_id String DEFAULT '',
    -- The three denormalized facets, so a ranked view needs no join: the agent, and
    -- the turn's own totals from the agents API, which are sums over every span in
    -- the turn rather than a per-span lookup. Everything else joins `spans`.
    agent_name LowCardinality(String) DEFAULT '',
    duration_ms UInt32 DEFAULT 0,
    cost_usd Float64 DEFAULT 0,

    -- Snapshot of the source turn's start, taken at extraction and never re-read,
    -- so it is the analysis clock rather than the pipeline clock.
    source_started_at DateTime64(6, 'UTC'),
    -- When the judge ran, which batching separates from when the row landed.
    extracted_at DateTime64(6, 'UTC'),
    -- The version. MATERIALIZED so no writer can supply one: there is a single
    -- clock, and a retry sorts later than the attempt it replaces.
    inserted_at DateTime64(6, 'UTC') MATERIALIZED now64(6),
    -- Retention only. Retraction uses a lightweight DELETE, because TTL is
    -- asynchronous and a row awaiting its merge still answers reads.
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(inserted_at)
-- Source month so retention and range reads follow user activity. PARTITION BY and
-- ORDER BY cannot be altered on a populated table, so they carry only what is
-- certain: tenancy, time, identity, and nothing about the pipeline.
PARTITION BY toYYYYMM(source_started_at)
-- toDate(source_started_at) precedes id so a sub-month read prunes granules.
ORDER BY (project_id, toDate(source_started_at), id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;


-- One detected failure per row: one conversation, one claim, one embedding, and
-- every turn the failure is attributed to.
CREATE TABLE IF NOT EXISTS failure_signatures
(
    project_id String,
    id UUID DEFAULT generateUUIDv7(),
    config_sha256 LowCardinality(String),

    -- The short canonical claim, and the judge's verbatim wording. See
    -- intent_signatures.signature.
    signature String,
    signature_display String DEFAULT '',
    -- Grounded prose explaining the claim. Never embedded, freely regenerable,
    -- which is why a rephrased rationale does not move a cluster.
    failure_reason String DEFAULT '',
    category LowCardinality(String),
    severity LowCardinality(String) DEFAULT '',
    vector Array(Float32),

    conversation_id String,
    -- First turn where it went wrong: the single anchor for ranking and drilldown.
    onset_trace_id String,
    -- Every turn the failure is attributed to, sorted and deduplicated by the
    -- writer, each joinable to spans.trace_id. Always contains onset_trace_id.
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
    inserted_at DateTime64(6, 'UTC') MATERIALIZED now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_conversation_id conversation_id TYPE bloom_filter(0.01) GRANULARITY 1,
    -- Serves has(trace_ids, {trace_id}), the drilldown from a turn to the failures
    -- touching it. Also covers onset_trace_id, always a member.
    INDEX idx_trace_ids trace_ids TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(source_started_at)
ORDER BY (project_id, toDate(source_started_at), id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
