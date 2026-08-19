-- A cluster run groups one signature type and exact extraction and clustering configs.
CREATE TABLE IF NOT EXISTS signature_cluster_runs
(
    project_id String,
    -- Intentionally omit UUID default, tracking in-progress runs requires re-inserting 
    -- with the same PK, consumers should generate uuidv7 before insert
    id UUID, -- UUIDv7

    signature_type Enum8('intent' = 1, 'failure' = 2),
    signature_config_sha LowCardinality(String),
    cluster_config_sha LowCardinality(String),
    naming_config_sha LowCardinality(String),

    window_start DateTime64(6, 'UTC'),
    window_end DateTime64(6, 'UTC'),

    status Enum8('pending' = 1, 'running' = 2, 'succeeded' = 3, 'failed' = 4, 'canceled' = 5)
        DEFAULT 'pending',

    started_at DateTime64(6, 'UTC'),
    completed_at DateTime64(6, 'UTC'),
    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00'
)
ENGINE = ReplacingMergeTree(inserted_at)
-- Every key column is fixed at run creation, so the terminal rewrite of `status` collapses
-- onto the running row instead of landing beside it.
ORDER BY (project_id, signature_type, window_end, id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

-- One generated label and occurrence count per cluster in a run.
CREATE TABLE IF NOT EXISTS signature_clusters
(
    project_id String,
    cluster_run_id UUID,
    id UUID,
    -- A cluster describes a run, not a turn, so the run window is its only time.
    -- Fixed at run creation, so it is partition-safe.
    run_window_end DateTime64(6, 'UTC'),
    -- Copied from the run. A cluster never spans types.
    signature_type Enum8('intent' = 1, 'failure' = 2),

    -- Not an FK: a topic identity carried forward by centroid match across runs, so it
    -- outlives the per-run `id`. Nil until the writer links a run to its predecessor.
    topic_id UUID,
    -- The signature category this cluster was fit within, empty when the run fit the
    -- whole space at once. Set by the clustering config's `scope`.
    category LowCardinality(String) DEFAULT '',
    -- Mean signature vector. Enables assigning a new signature to an existing cluster.
    centroid Array(Float32),

    label String,
    description String DEFAULT '',
    occurrence_count UInt64 DEFAULT 0,
    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_topic_id topic_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(run_window_end)
-- `centroid` and `occurrence_count` sit outside the key, so recentering a cluster
-- collapses onto the existing row.
ORDER BY (project_id, cluster_run_id, id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

-- One assignment per signature-table row in a run.
CREATE TABLE IF NOT EXISTS signature_cluster_assignments
(
    project_id String,
    cluster_run_id UUID,
    signature_record_id UUID,
    -- FK to `signature_clusters.id`. The nil uuid is noise, which has no cluster row.
    cluster_id UUID,
    signature_type Enum8('intent' = 1, 'failure' = 2),
    -- Copied from the signature row, so faceting a cluster by category needs no join.
    category LowCardinality(String) DEFAULT '',

    -- Distance from the signature vector to its cluster centroid.
    cluster_distance Float32 DEFAULT 0,
    -- HDBSCAN membership strength in [0, 1]. Zero on noise rows.
    cluster_probability Float32 DEFAULT 0,
    -- UMAP 2-D projection of the signature vector.
    umap_x Float32 DEFAULT 0,
    umap_y Float32 DEFAULT 0,

    -- `failure_signatures.current_trace_id` or `intent_signatures.trace_id`
    trace_id String,
    -- Required for join to spans.
    span_id String,
    conversation_id String,
    user_id String DEFAULT '',
    agent_name String DEFAULT '',
    -- Required for join to signatures and spans.
    trace_started_at DateTime64(6, 'UTC'),
    -- Source-turn end time, not insert time, so a late clustering run still windows.
    trace_ended_at DateTime64(6, 'UTC'),
    -- Whole-turn values copied onto every fan-out row. Divide by `turn_signature_count`
    -- to sum them, or group by `trace_id` first to credit the whole turn once.
    turn_duration_ms UInt32 DEFAULT 0,
    turn_cost_usd Float64 DEFAULT 0,
    -- Same vocabulary as the agent spans table, so no translation on the way in.
    turn_input_tokens UInt64 DEFAULT 0,
    turn_output_tokens UInt64 DEFAULT 0,
    turn_reasoning_tokens UInt64 DEFAULT 0,
    turn_cache_creation_input_tokens UInt64 DEFAULT 0,
    turn_cache_read_input_tokens UInt64 DEFAULT 0,
    -- Signatures the judge emitted for this turn. Defaults to 1, so an unset value
    -- leaves the columns above unapportioned instead of dividing by zero.
    turn_signature_count UInt16 DEFAULT 1,

    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_signature_record_id signature_record_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(inserted_at)
-- The turn's own time, matching the signature tables this row fans out from, so
-- retention and time-windowed reads are partition work rather than a scan.
PARTITION BY toYYYYMM(trace_started_at)
-- A signature holds one assignment per run, so `cluster_id` stays out of the key and
-- a rewrite that moves the signature collapses onto the existing row.
ORDER BY (project_id, cluster_run_id, signature_record_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

-- Conversation-ordered copy of the assignments, for the conversation-keyed reads the
-- UI routes on. Same identity columns, so a rewrite collapses here too.
CREATE TABLE IF NOT EXISTS signature_cluster_assignments_by_conversation
(
    project_id String,
    conversation_id String,
    cluster_run_id UUID,
    signature_record_id UUID,
    cluster_id UUID,
    signature_type Enum8('intent' = 1, 'failure' = 2),
    category LowCardinality(String) DEFAULT '',

    cluster_distance Float32 DEFAULT 0,
    cluster_probability Float32 DEFAULT 0,
    umap_x Float32 DEFAULT 0,
    umap_y Float32 DEFAULT 0,

    trace_id String,
    span_id String,
    user_id String DEFAULT '',
    agent_name String DEFAULT '',
    trace_started_at DateTime64(6, 'UTC'),
    trace_ended_at DateTime64(6, 'UTC'),
    turn_duration_ms UInt32 DEFAULT 0,
    turn_cost_usd Float64 DEFAULT 0,
    turn_input_tokens UInt64 DEFAULT 0,
    turn_output_tokens UInt64 DEFAULT 0,
    turn_reasoning_tokens UInt64 DEFAULT 0,
    turn_cache_creation_input_tokens UInt64 DEFAULT 0,
    turn_cache_read_input_tokens UInt64 DEFAULT 0,
    turn_signature_count UInt16 DEFAULT 1,

    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00'
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(trace_started_at)
ORDER BY (project_id, conversation_id, cluster_run_id, signature_record_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

CREATE MATERIALIZED VIEW IF NOT EXISTS signature_cluster_assignments_by_conversation_mv
TO signature_cluster_assignments_by_conversation AS
SELECT
    project_id,
    conversation_id,
    cluster_run_id,
    signature_record_id,
    cluster_id,
    signature_type,
    category,
    cluster_distance,
    cluster_probability,
    umap_x,
    umap_y,
    trace_id,
    span_id,
    user_id,
    agent_name,
    trace_started_at,
    trace_ended_at,
    turn_duration_ms,
    turn_cost_usd,
    turn_input_tokens,
    turn_output_tokens,
    turn_reasoning_tokens,
    turn_cache_creation_input_tokens,
    turn_cache_read_input_tokens,
    turn_signature_count,
    inserted_at,
    expire_at
FROM signature_cluster_assignments;

-- Added here because 041 has shipped. Token columns are one per category, not a
-- map, so a rollup can sum them with SimpleAggregateFunction.
ALTER TABLE intent_signatures
    ADD COLUMN IF NOT EXISTS turn_input_tokens UInt64 DEFAULT 0 AFTER turn_cost_usd,
    ADD COLUMN IF NOT EXISTS turn_output_tokens UInt64 DEFAULT 0 AFTER turn_input_tokens,
    ADD COLUMN IF NOT EXISTS turn_reasoning_tokens UInt64 DEFAULT 0 AFTER turn_output_tokens,
    ADD COLUMN IF NOT EXISTS turn_cache_creation_input_tokens UInt64 DEFAULT 0
        AFTER turn_reasoning_tokens,
    ADD COLUMN IF NOT EXISTS turn_cache_read_input_tokens UInt64 DEFAULT 0
        AFTER turn_cache_creation_input_tokens,
    -- Divisor that makes the whole-turn columns above additive across fan-out rows.
    ADD COLUMN IF NOT EXISTS turn_signature_count UInt16 DEFAULT 1
        AFTER turn_cache_read_input_tokens,
    ADD COLUMN IF NOT EXISTS trace_ended_at DateTime64(6, 'UTC') AFTER trace_started_at,
    -- Required for join to spans.
    ADD COLUMN IF NOT EXISTS span_id String AFTER trace_id;

-- Supersedes 041's note on this table: every `turn_` column describes the turn in
-- `current_trace_id`, so it means what the same column means on `intent_signatures`.
ALTER TABLE failure_signatures
    ADD COLUMN IF NOT EXISTS turn_input_tokens UInt64 DEFAULT 0 AFTER turn_cost_usd,
    ADD COLUMN IF NOT EXISTS turn_output_tokens UInt64 DEFAULT 0 AFTER turn_input_tokens,
    ADD COLUMN IF NOT EXISTS turn_reasoning_tokens UInt64 DEFAULT 0 AFTER turn_output_tokens,
    ADD COLUMN IF NOT EXISTS turn_cache_creation_input_tokens UInt64 DEFAULT 0
        AFTER turn_reasoning_tokens,
    ADD COLUMN IF NOT EXISTS turn_cache_read_input_tokens UInt64 DEFAULT 0
        AFTER turn_cache_creation_input_tokens,
    ADD COLUMN IF NOT EXISTS turn_signature_count UInt16 DEFAULT 1
        AFTER turn_cache_read_input_tokens,
    ADD COLUMN IF NOT EXISTS trace_ended_at DateTime64(6, 'UTC') AFTER trace_started_at,
    -- Required for join to spans.
    ADD COLUMN IF NOT EXISTS span_id String AFTER current_trace_id;
