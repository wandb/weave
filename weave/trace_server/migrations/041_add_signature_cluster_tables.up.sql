-- Cluster assignment, kept off the signature row it describes.
--
-- Signatures are appended continuously. Clustering is a periodic batch that
-- cannot know its answer when a signature is written, so an assignment on the
-- signature row would leave no way to write a complete row at insert time and
-- would force the clustering job to rewrite rows it has no other reason to
-- touch.
--
-- Assignments are keyed on the signature row id, so a run assigns exactly the
-- rows it clustered and nothing else. The consequence is that a row written
-- after a run has no assignment until the next run, including a repeat of text
-- that run already clustered. Keying on a hash of the signature text instead
-- would resolve those repeats with no backfill, at the cost of a hash column
-- and a second identity to keep canonical. The backfill wait is acceptable
-- because the dashboards read intent_cluster_daily, which is itself run-scoped
-- and therefore does not reflect post-run rows either way.
--
-- A run covers exactly one lens and its id is opaque, so lens stays out of every
-- child key. The lens on the runs row is also what says which table a run's
-- signature_row_ids point at: intent_signatures or failure_signatures.
--
-- A run's children are immutable: signature_clusters,
-- signature_cluster_assignments, and signature_cluster_daily are plain MergeTree
-- with no version column. A retry is a new run id, never a rewrite, so nothing
-- needs replacing and no read needs FINAL. Only signature_cluster_runs has a
-- lifecycle, and it holds one row per attempt. ReplacingMergeTree plus
-- deduplicate_merge_projection_mode='rebuild' would also have allowed the
-- projection below while keeping replacement. The immutable design is a choice,
-- not a platform constraint, and 'rebuild' is the escape hatch if insert tokens
-- prove insufficient.
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
--     expires no earlier than the signatures it folded, since once those age
--     out it is the only surviving record and cannot be recomputed.
--  4. signature_clusters.occurrence_count against sum(signature_cluster_daily
--     .occurrences) for a run is a free duplicate-insert alarm. They are
--     written from the same fold, so a mismatch means a retry landed twice.
--  5. The signature tables are ReplacingMergeTree read without FINAL, so the
--     fold MUST collapse a row's versions with GROUP BY id plus argMax before
--     counting it. Counting raw rows double-counts every retried insert.

-- One row per clustering run attempt. Holds the run's parameters and status,
-- which a per-cluster row cannot represent while a run is in flight or failed.
CREATE TABLE IF NOT EXISTS signature_cluster_runs
(
    project_id String,
    cluster_run_id String,                   -- opaque, unique per attempt, covers one lens
    -- No DEFAULT, and out of the sorting key on purpose. The children key on
    -- cluster_run_id alone, so if lens were part of this table's identity two
    -- lenses could share one run id here while their children merged into one
    -- indistinguishable pile. Keying on the id alone makes that collision a
    -- collapse you would notice.
    lens LowCardinality(String),
    -- The extraction config the clustered rows were written under, matching
    -- config_sha on intent_signatures and failure_signatures. One column rather
    -- than a pipeline version plus an embedding model, because upstream already
    -- collapses all pipeline state into this digest.
    --
    -- Comparing it against a row's own config_sha is what tells a reader whether
    -- that row shares a vector space with the run that clustered it. The check
    -- is conservative: two configs differing only in judge prompt embed
    -- identically but do not share a digest, so it reports a mismatch that does
    -- not exist. Digesting the embedding block alone would be exact, and is not
    -- worth a second digest concept for a rare false alarm.
    config_sha LowCardinality(String),
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
    --       FROM signature_cluster_runs
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
-- once rather than repeated onto every member row. Both counts are run-level and
-- therefore safe to read directly, unlike a per-day count.
CREATE TABLE IF NOT EXISTS signature_clusters
(
    project_id String,
    cluster_run_id String,
    cluster_id Int32,
    label String DEFAULT '',
    description String DEFAULT '',
    -- Distinct signature texts in the cluster, against occurrence_count's total
    -- assigned rows. Both are folded by the run.
    signature_count UInt32 DEFAULT 0,
    occurrence_count UInt64 DEFAULT 0,
    centroid Array(Float32),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00'
)
ENGINE = MergeTree
ORDER BY (project_id, cluster_run_id, cluster_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0, non_replicated_deduplication_window = 1000;

-- Cluster membership, one row per (run, signature row).
--
-- The base order answers "which cluster holds this row" from the key prefix.
-- proj_by_cluster answers the reverse, "which rows are in this cluster", as a
-- contiguous range read instead of a scan of the whole run. Immutability is what
-- makes the projection free: ClickHouse refuses one on ReplacingMergeTree unless
-- deduplicate_merge_projection_mode is 'drop' or 'rebuild', and 'rebuild' would
-- reproject on every dedup merge.
CREATE TABLE IF NOT EXISTS signature_cluster_assignments
(
    project_id String,
    cluster_run_id String,
    -- id of the row in intent_signatures or failure_signatures. Which table is
    -- decided by the run's lens, so no lens column appears here.
    signature_row_id UUID,
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
        SELECT project_id, cluster_run_id, cluster_id, signature_row_id,
               cluster_confidence, umap_x, umap_y
        ORDER BY (project_id, cluster_run_id, cluster_id, signature_row_id)
    )
)
ENGINE = MergeTree
ORDER BY (project_id, cluster_run_id, signature_row_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0, non_replicated_deduplication_window = 1000;

-- Cluster-level daily rollup, written by the clustering job at the end of a run
-- by folding the signature rows through that run's assignments. Cluster
-- membership is unknown at insert time, so this cannot be a materialized view.
-- Producing it is the last step of the run that defines it.
--
-- This is what the cluster dashboards read. Doing the row-to-cluster fold once
-- per run instead of once per page load is what keeps those reads flat as the
-- signature tables grow.
--
-- Every distinct-entity column is a mergeable state, so a day range aggregates
-- without double counting an entity that appears on more than one day. A plain
-- per-day integer would be wrong for exactly that reason. occurrences is a plain
-- sum because a signature row belongs to one day only.
--
-- signatures counts distinct signature TEXT, not distinct rows: rows are already
-- counted by occurrences, and the interesting number is how much distinct
-- phrasing a cluster covers. uniqHLL12 hashes internally, so passing the text
-- costs nothing over passing a hash of it.
--
-- uniqHLL12 rather than uniq is a deliberate trade, not a free win. It is a flat
-- 2.6 KB state at any cardinality: at the head that is the difference between
-- 4 KB and 18 KB per row and a tenfold cut in the memory a reach query merges,
-- but for a cluster-day with only tens of distinct users it is ~6x larger than
-- uniq would be, and it is approximate above ~1k distinct (~3% at 10k) where
-- uniq is exact. Bounding the worst case is worth it on a shared server, and the
-- choice is permanent: once the signature rows age out this rollup is the only
-- record and cannot be recomputed under a different aggregate.
CREATE TABLE IF NOT EXISTS signature_cluster_daily
(
    project_id String,
    cluster_run_id String,
    day Date,
    cluster_id Int32,
    occurrences UInt64 DEFAULT 0,
    signatures AggregateFunction(uniqHLL12, String),
    users AggregateFunction(uniqHLL12, String),
    conversations AggregateFunction(uniqHLL12, String),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (project_id, cluster_run_id, day, cluster_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0, non_replicated_deduplication_window = 1000;
