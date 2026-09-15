-- A user's assertion that one topic matters, holding the composition they pinned.
CREATE TABLE IF NOT EXISTS signature_topic_pins
(
    project_id String,
    -- Copied from the run that produced the topic. A topic never spans types.
    signature_type Enum8('intent' = 1, 'failure' = 2),
    -- Matches `signature_clusters.topic_id`, which outlives any one run's cluster id.
    topic_id UUID,

    -- `signature_cluster_assignments.signature_record_id`s of the cluster the topic held
    -- when it was pinned. Reconciliation scores against this as well as the previous run,
    -- which is what bounds how far a pinned topic drifts from what the user pinned.
    anchor_members Array(UUID),
    -- The name those members carried. A pin that reattaches after a dormant run resumes
    -- under it instead of being renamed, and a rebase decision is reviewable against it.
    anchor_label String DEFAULT '',
    anchor_description String DEFAULT '',
    -- `signature_clusters.centroid` of that cluster. A claiming cluster's centroid must sit
    -- within the configured cosine distance of it, whatever its member overlap says.
    anchor_centroid Array(Float32) DEFAULT [],
    -- When the user pinned or last rebased. Distinct from `inserted_at`, which versions
    -- the row: a retried write of the same rebase keeps one `pinned_at`.
    pinned_at DateTime64(6, 'UTC'),

    inserted_at DateTime64(6, 'UTC') DEFAULT now64(6),
    expire_at DateTime DEFAULT '2100-01-01 00:00:00'
)
ENGINE = ReplacingMergeTree(inserted_at)
-- Every key column is fixed at pin time, so a rebase collapses onto the pinned row
-- instead of landing beside it. Unpartitioned: one row per pinned topic per project.
ORDER BY (project_id, signature_type, topic_id)
TTL expire_at DELETE
SETTINGS min_bytes_for_wide_part = 0;
