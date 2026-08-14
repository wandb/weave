-- A cluster run groups one signature type and exact extraction and clustering configs.
CREATE TABLE IF NOT EXISTS signature_cluster_runs
(
    project_id String,
    id UUID DEFAULT generateUUIDv7(),
    signature_type Enum8('intent' = 1, 'failure' = 2),
    signature_config_sha LowCardinality(String),
    cluster_config_sha LowCardinality(String),
    window_start DateTime64(6, 'UTC'),
    window_end DateTime64(6, 'UTC'),
    status Enum8('running' = 1, 'completed' = 2, 'failed' = 3) DEFAULT 'running',
    started_at DateTime64(6, 'UTC'),
    -- NULL until the run terminates. `inserted_at` is the merge version, not a finish time.
    completed_at Nullable(DateTime64(6, 'UTC')) DEFAULT NULL,
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
    -- The clusterer's own label, dense from 0 and unique only within `cluster_run_id`. A run
    -- relabels from scratch, so this never identifies the same cluster across two runs.
    cluster_id Int32,
    label String,
    occurrence_count UInt64 DEFAULT 0,
    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00'
)
ENGINE = ReplacingMergeTree(inserted_at)
-- `(cluster_run_id, cluster_id)` is the natural key, so a retried run collapses rather than
-- double-counting `occurrence_count`.
ORDER BY (project_id, cluster_run_id, cluster_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

-- One assignment per signature-table row in a run.
CREATE TABLE IF NOT EXISTS signature_cluster_assignments
(
    project_id String,
    cluster_run_id UUID,
    signature_record_id UUID,
    -- -1 is noise, which has no `signature_clusters` row.
    cluster_id Int32 DEFAULT -1,
    -- Distance from the signature vector to its cluster centroid, 0 for noise rows.
    cluster_distance Float32 DEFAULT 0,
    -- UMAP 2-D projection of the signature vector, reprojected by every run.
    umap_x Float32 DEFAULT 0,
    umap_y Float32 DEFAULT 0,

    -- Denormalized from the signature row so cluster aggregates need no join.
    -- The turn the signature was extracted from, `failure_signatures.current_trace_id` for
    -- failures. Join to hydrate `affected_trace_ids`, which is not copied.
    trace_id String,
    -- Whole-turn values copied onto every fan-out row, so summing them across a cluster
    -- without first deduplicating on `trace_id` overcounts.
    turn_duration_ms UInt32 DEFAULT 0,
    turn_cost_usd Float64 DEFAULT 0,

    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00'
)
ENGINE = ReplacingMergeTree(inserted_at)
ORDER BY (project_id, cluster_run_id, signature_record_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
