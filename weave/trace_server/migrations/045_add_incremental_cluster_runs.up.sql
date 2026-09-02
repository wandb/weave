-- How the run produced its partition. `incremental` carries the anchor run's topics,
-- attaches new signatures by centroid, and fits only the residue.
ALTER TABLE signature_cluster_runs
    ADD COLUMN IF NOT EXISTS mode Enum8('full' = 1, 'incremental' = 2) DEFAULT 'full'
        AFTER naming_config_sha,
    -- The succeeded run whose topics this run carried. Nil on a `full` run.
    ADD COLUMN IF NOT EXISTS anchor_run_id UUID DEFAULT toUUID('00000000-0000-0000-0000-000000000000')
        AFTER mode;

-- Cosine similarity to `centroid` a new signature must clear to join this topic in
-- the next incremental run. Zero means the writer never computed one.
ALTER TABLE signature_clusters
    ADD COLUMN IF NOT EXISTS attach_radius Float32 DEFAULT 0 AFTER centroid,
    -- Topics this cluster split from or merged out of. Empty on continuations and births.
    ADD COLUMN IF NOT EXISTS parent_topic_ids Array(UUID) DEFAULT [] AFTER topic_id;
