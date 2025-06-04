ALTER TABLE object_versions_stats_view MODIFY QUERY
SELECT
    object_versions.project_id,
    object_versions.kind,
    object_versions.object_id,
    object_versions.digest,
    anySimpleState(object_versions.base_object_class) AS base_object_class,
    anySimpleState(length(object_versions.val_dump)) AS size_bytes,
    minSimpleState(object_versions.created_at) AS created_at,
    maxSimpleState(object_versions.created_at) AS updated_at
FROM object_versions
GROUP BY
    object_versions.project_id,
    object_versions.kind,
    object_versions.object_id,
    object_versions.digest;

ALTER TABLE object_versions
    DROP COLUMN leaf_object_class;

ALTER TABLE object_versions_stats
    DROP COLUMN leaf_object_class;
