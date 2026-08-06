CREATE TABLE IF NOT EXISTS cluster_results
(
    project_id String,
    job_id String,
    intent_id String,
    input_version UInt64,
    cluster_id Int32,
    probability Float32,
    created_at DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = MergeTree
PARTITION BY cityHash64(project_id) % 32
ORDER BY (project_id, job_id, intent_id);
