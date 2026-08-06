CREATE TABLE IF NOT EXISTS cluster_jobs
(
    project_id String,
    job_id String,
    version UInt64,
    status LowCardinality(String),
    min_cluster_size UInt16,
    vector_count Nullable(UInt32),
    error_code Nullable(String),
    created_by_user_id String,
    created_at DateTime64(6, 'UTC'),
    started_at Nullable(DateTime64(6, 'UTC')),
    completed_at Nullable(DateTime64(6, 'UTC'))
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY cityHash64(project_id) % 32
ORDER BY (project_id, job_id);
