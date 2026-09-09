ALTER TABLE signature_clusters
    DROP COLUMN IF EXISTS parent_topic_ids;

ALTER TABLE signature_cluster_runs
    DROP COLUMN IF EXISTS continuity_config,
    DROP COLUMN IF EXISTS anchor_run_id,
    DROP COLUMN IF EXISTS mode;
