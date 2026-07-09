ALTER TABLE object_versions
    ADD COLUMN IF NOT EXISTS wb_user_id Nullable(String) DEFAULT NULL;

ALTER TABLE object_versions_stats
    ADD COLUMN IF NOT EXISTS wb_user_id Nullable(String) DEFAULT NULL;
