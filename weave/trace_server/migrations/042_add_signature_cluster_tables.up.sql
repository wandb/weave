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
    -- Copied from the run. Fixed at run creation, so it is partition-safe.
    run_window_end DateTime64(6, 'UTC'),

    -- Not an FK: a topic identity carried forward by centroid match across runs, so it
    -- outlives the per-run `id`. Nil until the writer links a run to its predecessor.
    topic_id UUID,
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
ORDER BY (project_id, cluster_run_id, id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

-- One assignment per signature-table row in a run.
CREATE TABLE IF NOT EXISTS signature_cluster_assignments
(
    project_id String,
    cluster_run_id UUID,
    signature_record_id UUID,
    -- FK to `signature_cluster_runs.window_end`.
    run_window_end DateTime64(6, 'UTC'),
    -- FK to `signature_clusters.id`. The nil uuid is noise, which has no cluster row,
    -- so a run's noise rows are one contiguous range of the sorting key.
    cluster_id UUID,
    signature_type Enum8('intent' = 1, 'failure' = 2),

    -- Distance from the signature vector to its cluster centroid.
    cluster_distance Float32 DEFAULT 0,
    -- UMAP 2-D projection of the signature vector.
    umap_x Float32 DEFAULT 0,
    umap_y Float32 DEFAULT 0,

    -- `failure_signatures.current_trace_id` or `intent_signatures.trace_id`
    trace_id String,
    -- Whole-turn values copied onto every fan-out row, so summing them overcounts a
    -- cluster that holds more than one signature from the same turn.
    turn_duration_ms UInt32 DEFAULT 0,
    turn_cost_usd Float64 DEFAULT 0,
    -- Same vocabulary as the agent spans table, so no translation on the way in.
    turn_input_tokens UInt64 DEFAULT 0,
    turn_output_tokens UInt64 DEFAULT 0,
    turn_reasoning_tokens UInt64 DEFAULT 0,
    turn_cache_creation_input_tokens UInt64 DEFAULT 0,
    turn_cache_read_input_tokens UInt64 DEFAULT 0,

    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    INDEX idx_signature_record_id signature_record_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(run_window_end)
ORDER BY (project_id, cluster_run_id, cluster_id, signature_record_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

-- Tokens for the turn each signature came from, added here because 041 has shipped.
-- One column per category, not a map, so a rollup can sum them with SimpleAggregateFunction.
ALTER TABLE intent_signatures
    ADD COLUMN IF NOT EXISTS turn_input_tokens UInt64 DEFAULT 0 AFTER turn_cost_usd,
    ADD COLUMN IF NOT EXISTS turn_output_tokens UInt64 DEFAULT 0 AFTER turn_input_tokens,
    ADD COLUMN IF NOT EXISTS turn_reasoning_tokens UInt64 DEFAULT 0 AFTER turn_output_tokens,
    ADD COLUMN IF NOT EXISTS turn_cache_creation_input_tokens UInt64 DEFAULT 0
        AFTER turn_reasoning_tokens,
    ADD COLUMN IF NOT EXISTS turn_cache_read_input_tokens UInt64 DEFAULT 0
        AFTER turn_cache_creation_input_tokens;

ALTER TABLE failure_signatures
    ADD COLUMN IF NOT EXISTS turn_input_tokens UInt64 DEFAULT 0 AFTER turn_cost_usd,
    ADD COLUMN IF NOT EXISTS turn_output_tokens UInt64 DEFAULT 0 AFTER turn_input_tokens,
    ADD COLUMN IF NOT EXISTS turn_reasoning_tokens UInt64 DEFAULT 0 AFTER turn_output_tokens,
    ADD COLUMN IF NOT EXISTS turn_cache_creation_input_tokens UInt64 DEFAULT 0
        AFTER turn_reasoning_tokens,
    ADD COLUMN IF NOT EXISTS turn_cache_read_input_tokens UInt64 DEFAULT 0
        AFTER turn_cache_creation_input_tokens;
