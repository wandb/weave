CREATE TABLE IF NOT EXISTS db_management.backfills (
    backfill_id String,
    migration_version UInt64,
    db_name String,
    status String,
    checkpoint_data String,
    rows_processed UInt64 DEFAULT 0,
    started_at Nullable(DateTime64(3)),
    updated_at DateTime64(3) DEFAULT now64(3),
    completed_at Nullable(DateTime64(3)),
    error_log Nullable(String)
) ENGINE = MergeTree()
ORDER BY (db_name, migration_version);
