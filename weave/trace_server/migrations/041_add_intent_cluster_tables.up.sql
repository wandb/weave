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
-- signature_id carries no pipeline_version, so that reuse crosses recipe
-- versions on purpose: identical canonical text is the same intent whichever
-- recipe extracted it. The consequence is that an occurrence extracted under a
-- new embedding model inherits a cluster computed in the old vector space. A
-- reader that cannot tolerate that compares intent_cluster_runs.pipeline_version
-- and embedding_model against the occurrence. Nothing in the key stops it.
--
-- A run covers exactly one lens and its id is opaque, so lens stays out of every
-- child key. signature_id is itself lens-scoped (see 040), which is what lets
-- the child tables key on (run, signature_id) with no lens column at all.
--
-- A run's children are immutable: intent_clusters, intent_cluster_assignments,
-- and intent_cluster_daily are plain MergeTree with no version column. A retry
-- is a new run id, never a rewrite, so nothing needs replacing and no read needs
-- FINAL. Only intent_cluster_runs has a lifecycle, and it holds one row per
-- attempt. ReplacingMergeTree plus deduplicate_merge_projection_mode='rebuild'
-- would also have allowed the projection below while keeping replacement. The
-- immutable design is a choice, not a platform constraint, and 'rebuild' is the
-- escape hatch if insert tokens prove insufficient.
--
-- WRITER CONTRACT, because none of this can be enforced in DDL:
--
--  1. Immutability removes replacement, which was the only thing making a
--     retried INSERT idempotent. A duplicated row silently doubles
--     occurrences, and a duplicated assignment doubles it again through the
--     fold's join. Every insert to a child table MUST carry
--     insert_deduplication_token, keyed on the run id, table, and batch
--     sequence. non_replicated_deduplication_window below is what makes that
--     token effective on the non-replicated path. The replicated engines get
--     it from replicated_deduplication_window. Block-checksum dedup alone does
--     not cover this: now64() defaults make two logically identical inserts
--     different blocks.
--  2. An abandoned attempt is never repaired. Its children live until
--     expire_at, so the clustering job owns reclaim:
--     ALTER TABLE ... DELETE WHERE cluster_run_id IN (<abandoned>). Because
--     expire_at is written at insert time onto immutable rows, retention is
--     chosen before promotion and cannot be extended afterwards, so give every
--     attempt full retention and sweep the losers. PARTITION BY cluster_run_id
--     would make that a metadata-only DROP PARTITION, and is rejected:
--     projects times attempts is partition explosion.
--  3. expire_at ordering is a writer invariant. Children expire no earlier
--     than their runs row, or the run points at data that is gone. The rollup
--     expires no earlier than the occurrences it folded, since once those age
--     out it is the only surviving record and cannot be recomputed.
--  4. intent_clusters.occurrence_count against sum(intent_cluster_daily
--     .occurrences) for a run is a free duplicate-insert alarm. They are
--     written from the same fold, so a mismatch means a retry landed twice.

-- One row per clustering run attempt. Holds the run's parameters and status,
-- which a per-cluster row cannot represent while a run is in flight or failed.
CREATE TABLE IF NOT EXISTS intent_cluster_runs
(
    project_id String,
    cluster_run_id String,                   -- opaque, unique per attempt, covers one lens
    -- No DEFAULT, and out of the sorting key on purpose. The children key on
    -- cluster_run_id alone, so if lens were part of this table's identity two
    -- lenses could share one run id here while their children merged into one
    -- indistinguishable pile. Keying on the id alone makes that collision a
    -- collapse you would notice.
    lens LowCardinality(String),
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
    -- Explicit promotion pointer, so an unpromoted experimental run can never go
    -- live by being newest. Zero means never promoted, and promoted_at is the
    -- authoritative signal: status stays for observability.
    --
    -- Readers MUST collapse versions before ordering, never max(promoted_at)
    -- across raw rows. This table is ReplacingMergeTree read without FINAL, so
    -- unmerged old versions still carry the old value and a max() cannot see it
    -- was superseded, which reports a demoted run as live:
    --   SELECT cluster_run_id FROM (
    --       SELECT cluster_run_id,
    --              argMax(status, record_version) AS status,
    --              argMax(promoted_at, record_version) AS promoted_at
    --       FROM intent_cluster_runs
    --       WHERE project_id = ? AND lens = ?
    --       GROUP BY cluster_run_id)
    --   WHERE promoted_at > toDateTime64(0, 3, 'UTC')
    --   ORDER BY promoted_at DESC LIMIT 1
    promoted_at DateTime64(3, 'UTC') DEFAULT toDateTime64(0, 3, 'UTC'),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',
    record_version UInt64
)
ENGINE = ReplacingMergeTree(record_version)
ORDER BY (project_id, cluster_run_id)
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
SETTINGS min_bytes_for_wide_part = 0, non_replicated_deduplication_window = 1000;

-- Cluster membership, one row per (run, signature).
--
-- The base order answers "which cluster holds this signature" from the key
-- prefix. proj_by_cluster answers the reverse, "which signatures are in this
-- cluster", as a contiguous range read instead of a scan of the whole run.
-- Immutability is what makes the projection free: ClickHouse refuses one on
-- ReplacingMergeTree unless deduplicate_merge_projection_mode is 'drop' or
-- 'rebuild', and 'rebuild' would reproject on every dedup merge.
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
SETTINGS min_bytes_for_wide_part = 0, non_replicated_deduplication_window = 1000;

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
-- uniqHLL12 rather than uniq is a deliberate trade, not a free win. It is a flat
-- 2.6 KB state at any cardinality: at the head that is the difference between
-- 4 KB and 18 KB per row and a tenfold cut in the memory a reach query merges,
-- but for a cluster-day with only tens of distinct users it is ~6x larger than
-- uniq would be, and it is approximate above ~1k distinct (~3% at 10k) where
-- uniq is exact. Bounding the worst case is worth it on a shared server, and the
-- choice is permanent: once occurrences age out this rollup is the only record
-- and cannot be recomputed under a different aggregate.
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
SETTINGS min_bytes_for_wide_part = 0, non_replicated_deduplication_window = 1000;
