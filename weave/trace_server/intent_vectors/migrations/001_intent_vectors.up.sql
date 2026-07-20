CREATE TABLE IF NOT EXISTS intent_vectors
(
    project_id String,
    intent_id String,
    version UInt64,
    deleted Bool,
    signature String,
    normalized_signature String,
    request_type LowCardinality(String),
    status LowCardinality(String),
    source LowCardinality(String),
    source_id String,
    role LowCardinality(String),
    event_time DateTime64(6, 'UTC'),
    attributes Map(String, String),
    embedding_model LowCardinality(String),
    embedding_dimensions UInt16,
    vector Array(Float32),
    created_by_user_id String,
    created_at DateTime64(6, 'UTC'),
    INDEX ann vector TYPE vector_similarity('hnsw', 'cosineDistance', 1024, 'bf16', 64, 512) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY cityHash64(project_id) % 32
ORDER BY (project_id, intent_id);
