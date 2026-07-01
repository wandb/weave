ALTER TABLE object_versions
    DROP COLUMN IF EXISTS wb_user_id;

ALTER TABLE object_versions_stats
    DROP COLUMN IF EXISTS wb_user_id;
