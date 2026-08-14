CREATE TABLE IF NOT EXISTS cluster_action_items
(
    project_id String,
    cluster_run_id UUID,
    cluster_id UUID,
    -- Copied from the cluster run so Action Items share its lifecycle partition.
    run_window_end DateTime64(6, 'UTC'),
    signature_type Enum8('intent' = 1, 'failure' = 2),

    -- The writer reuses this UUID for retries and later user edits.
    id UUID,
    action_item_config_sha LowCardinality(String),

    title String,
    description String DEFAULT '',
    evidence_trace_ids Array(String) DEFAULT [],
    status Enum8('OPEN' = 1, 'IN_PROGRESS' = 2, 'COMPLETED' = 3, 'DISMISSED' = 4)
        DEFAULT 'OPEN',
    severity Enum8('SEVERE' = 1, 'MAJOR' = 2, 'MINOR' = 3) DEFAULT 'MINOR',

    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00'
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(run_window_end)
ORDER BY (project_id, cluster_run_id, cluster_id, id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
