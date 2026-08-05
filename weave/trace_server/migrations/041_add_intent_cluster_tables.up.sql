-- Cluster assignment, kept off the occurrence row it describes.
--
-- Occurrences are appended continuously. Clustering is a periodic batch that
-- cannot know its answer when an occurrence is written, so an assignment on the
-- occurrence row would leave no way to write a complete row at insert time and
-- would force the clustering job to rewrite occurrences it has no other reason
-- to touch.
--
-- Assignments are keyed on signature_id rather than on the occurrence id, so a
-- new occurrence of an already-clustered signature resolves to its cluster with
-- no backfill. Only genuinely novel signatures wait for the next run.

-- One row per clustering run. Holds the run's parameters and status, which a
-- per-cluster row cannot represent while a run is in flight or has failed.
CREATE TABLE IF NOT EXISTS intent_cluster_runs
(
    project_id String,
    cluster_run_id String,
    lens LowCardinality(String) DEFAULT 'intent',
    pipeline_version UInt32,
    embedding_model LowCardinality(String),
    algorithm LowCardinality(String) DEFAULT '',
    algorithm_params String DEFAULT '',      -- JSON blob, stored not queried
    window_start DateTime64(6, 'UTC'),       -- source-time bounds of the clustered input
    window_end DateTime64(6, 'UTC'),
    status LowCardinality(String) DEFAULT 'running',  -- running | complete | failed
    signature_count UInt32 DEFAULT 0,
    cluster_count UInt32 DEFAULT 0,
    started_at DateTime64(3, 'UTC') DEFAULT now64(3),
    completed_at DateTime64(3, 'UTC') DEFAULT toDateTime64(0, 3, 'UTC'),
    record_version UInt64
)
ENGINE = ReplacingMergeTree(record_version)
ORDER BY (project_id, lens, cluster_run_id)
SETTINGS min_bytes_for_wide_part = 0;

-- Per-cluster metadata for one run. The generated label and centroid live here
-- once rather than repeated onto every member row.
CREATE TABLE IF NOT EXISTS intent_clusters
(
    project_id String,
    cluster_run_id String,
    cluster_id Int32,
    label String DEFAULT '',
    description String DEFAULT '',
    signature_count UInt32 DEFAULT 0,
    occurrence_count UInt64 DEFAULT 0,
    centroid Array(Float32),
    record_version UInt64
)
ENGINE = ReplacingMergeTree(record_version)
ORDER BY (project_id, cluster_run_id, cluster_id)
SETTINGS min_bytes_for_wide_part = 0;

-- Cluster membership, one row per (run, signature).
--
-- cluster_id is deliberately NOT in the sorting key. ReplacingMergeTree
-- deduplicates on the full sorting key, so a retried run that moved a signature
-- to a different cluster would be stored as a second row instead of replacing
-- the first.
CREATE TABLE IF NOT EXISTS intent_cluster_assignments
(
    project_id String,
    cluster_run_id String,
    signature_id FixedString(16),
    cluster_id Int32 DEFAULT -1,             -- -1 is the HDBSCAN noise label
    cluster_confidence Float32 DEFAULT 0,
    -- UMAP 2D projection of the signature vector, for the cluster scatter plot.
    -- Run-scoped like cluster_id: a later run reprojects into different axes.
    umap_x Float32 DEFAULT 0,
    umap_y Float32 DEFAULT 0,
    assigned_at DateTime64(3, 'UTC') DEFAULT now64(3),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',
    record_version UInt64
)
ENGINE = ReplacingMergeTree(record_version)
ORDER BY (project_id, cluster_run_id, signature_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

-- Cluster-level daily rollup, written by the clustering job at the end of a run
-- by folding the occurrence counts through that run's assignments. Cluster
-- membership is unknown at occurrence-insert time, so this cannot be a
-- materialized view. Producing it is the last step of the run that defines it.
--
-- This is what the cluster dashboards read. Doing the signature-to-cluster fold
-- once per run instead of once per page load is what keeps those reads flat as
-- the occurrence table grows.
CREATE TABLE IF NOT EXISTS intent_cluster_daily
(
    project_id String,
    cluster_run_id String,
    lens LowCardinality(String) DEFAULT 'intent',
    day Date,
    cluster_id Int32,
    occurrences UInt64 DEFAULT 0,
    signature_count UInt32 DEFAULT 0,
    -- Kept as mergeable states so a day range aggregates without double
    -- counting a user who appears on more than one day.
    users AggregateFunction(uniq, String),
    conversations AggregateFunction(uniq, String),
    record_version UInt64
)
ENGINE = ReplacingMergeTree(record_version)
PARTITION BY toYYYYMM(day)
ORDER BY (project_id, cluster_run_id, lens, day, cluster_id)
SETTINGS min_bytes_for_wide_part = 0;
