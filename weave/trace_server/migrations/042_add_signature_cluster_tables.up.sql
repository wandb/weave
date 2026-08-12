-- A cluster run groups one signature type and exact extraction and clustering configs.
CREATE TABLE IF NOT EXISTS signature_cluster_runs
(
    project_id String,
    id UUID DEFAULT generateUUIDv7(),
    signature_type LowCardinality(String),
    signature_config_sha LowCardinality(String),
    cluster_config_sha LowCardinality(String),
    window_start DateTime64(6, 'UTC'),
    window_end DateTime64(6, 'UTC'),
    status LowCardinality(String) DEFAULT 'running',
    started_at DateTime64(6, 'UTC'),
    completed_at Nullable(DateTime64(6, 'UTC')) DEFAULT NULL,
    inserted_at DateTime64(6, 'UTC') DEFAULT now(),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00'
)
ENGINE = ReplacingMergeTree(inserted_at)
ORDER BY (project_id, id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

-- One generated label and occurrence count per cluster in a run.
CREATE TABLE IF NOT EXISTS signature_clusters
(
    project_id String,
    cluster_run_id UUID,
    cluster_id Int32,
    label String DEFAULT '',
    occurrence_count UInt64 DEFAULT 0,
    inserted_at DateTime64(6, 'UTC') DEFAULT now(),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00'
)
ENGINE = ReplacingMergeTree(inserted_at)
ORDER BY (project_id, cluster_run_id, cluster_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;

-- One assignment per signature-table row in a run.
CREATE TABLE IF NOT EXISTS signature_cluster_assignments
(
    project_id String,
    cluster_run_id UUID,
    signature_record_id UUID,
    cluster_id Int32 DEFAULT -1,
    cluster_confidence Float32 DEFAULT 0,
    inserted_at DateTime64(6, 'UTC') DEFAULT now(),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00'
)
ENGINE = ReplacingMergeTree(inserted_at)
ORDER BY (project_id, cluster_run_id, signature_record_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
