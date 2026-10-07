-- One embedding per distinct wording per embedding space, written at fit time.
CREATE TABLE IF NOT EXISTS signature_vectors
(
    project_id String,
    signature_type Enum8('intent' = 1, 'failure' = 2),
    -- Digest of the recipe's `embedding:` block: model, dimensions, instruction.
    space LowCardinality(String),
    signature String,
    vector Array(Float32),
    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT now() + INTERVAL 30 DAY
)
ENGINE = ReplacingMergeTree(inserted_at)
-- Every key column is fixed per wording, so a re-embed collapses onto the existing row.
ORDER BY (project_id, signature_type, space, signature)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
