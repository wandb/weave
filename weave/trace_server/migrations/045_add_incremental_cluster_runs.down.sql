ALTER TABLE signature_clusters
    DROP COLUMN IF EXISTS parent_topic_ids,
    DROP COLUMN IF EXISTS attach_radius;

ALTER TABLE signature_cluster_runs
    DROP COLUMN IF EXISTS anchor_run_id,
    DROP COLUMN IF EXISTS mode;
