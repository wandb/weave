ALTER TABLE object_versions
    ADD COLUMN wb_user_id Nullable(String) DEFAULT NULL;

ALTER TABLE object_versions_stats
    ADD COLUMN wb_user_id Nullable(String) DEFAULT NULL;
