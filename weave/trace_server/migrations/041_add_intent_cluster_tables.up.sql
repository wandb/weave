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
--
-- A run covers exactly one lens and its id is opaque, so lens stays out of every
-- child key. signature_id is itself lens-scoped (see 040), which is what lets
-- the child tables key on (run, signature_id) with no lens column at all.
--
-- A run's children are immutable: intent_clusters, intent_cluster_assignments,
-- and intent_cluster_daily are plain MergeTree with no version column. A retry
-- is a new run id, never a rewrite, so nothing needs replacing and no read needs
-- FINAL. A partially written run is abandoned and expired rather than repaired.
-- Only intent_cluster_runs has a lifecycle, and it holds one row per attempt.

-- One row per clustering run attempt. Holds the run's parameters and status,
-- which a per-cluster row cannot represent while a run is in flight or failed.
CREATE TABLE IF NOT EXISTS intent_cluster_runs
(
    project_id String,
    cluster_run_id String,                   -- opaque, unique per attempt, covers one lens
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
    -- Explicit promotion pointer. Readers take the run with the greatest
    -- promoted_at, so an unpromoted experimental run can never go live by being
    -- newest. Zero means never promoted.
    promoted_at DateTime64(3, 'UTC') DEFAULT toDateTime64(0, 3, 'UTC'),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',
    record_version UInt64
)
ENGINE = ReplacingMergeTree(record_version)
ORDER BY (project_id, lens, cluster_run_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

-- Per-cluster metadata for one run. The generated label and centroid live here
-- once rather than repeated onto every member row. signature_count is run-level
-- and therefore safe to read directly, unlike a per-day count.
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
    expire_at DateTime DEFAULT '2100-01-01 00:00:00'
)
ENGINE = MergeTree
ORDER BY (project_id, cluster_run_id, cluster_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

-- Cluster membership, one row per (run, signature).
--
-- The base order answers "which cluster holds this signature" from the key
-- prefix. proj_by_cluster answers the reverse, "which signatures are in this
-- cluster", as a contiguous range read instead of a scan of the whole run. A
-- projection is only possible because the table is immutable: ClickHouse
-- rejects projections on ReplacingMergeTree.
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

    PROJECTION proj_by_cluster
    (
        SELECT project_id, cluster_run_id, cluster_id, signature_id,
               cluster_confidence, umap_x, umap_y
        ORDER BY (project_id, cluster_run_id, cluster_id, signature_id)
    )
)
ENGINE = MergeTree
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
--
-- Every distinct-entity column is a mergeable state, so a day range aggregates
-- without double counting an entity that appears on more than one day. A plain
-- per-day integer would be wrong for exactly that reason. occurrences is a plain
-- sum because an occurrence belongs to one day only.
--
-- uniqHLL12 rather than uniq: a fixed small state instead of one that grows with
-- cardinality, which on this table is the difference between 4 KB and 18 KB per
-- row and a tenfold cut in the memory a reach query needs to merge them.
CREATE TABLE IF NOT EXISTS intent_cluster_daily
(
    project_id String,
    cluster_run_id String,
    day Date,
    cluster_id Int32,
    occurrences UInt64 DEFAULT 0,
    signatures AggregateFunction(uniqHLL12, FixedString(16)),
    users AggregateFunction(uniqHLL12, String),
    conversations AggregateFunction(uniqHLL12, String),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (project_id, cluster_run_id, day, cluster_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
