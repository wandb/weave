ALTER TABLE object_versions
    ADD COLUMN leaf_object_class Nullable(String) DEFAULT NULL;

ALTER TABLE object_versions_stats
    ADD COLUMN leaf_object_class SimpleAggregateFunction(any, Nullable(String));

ALTER TABLE object_versions_stats_view MODIFY QUERY
SELECT
    object_versions.project_id,
    object_versions.kind,
    object_versions.object_id,
    object_versions.digest,
    anySimpleState(object_versions.base_object_class) AS base_object_class,
    anySimpleState(object_versions.leaf_object_class) AS leaf_object_class,
    anySimpleState(object_versions.wb_user_id) AS wb_user_id,
    anySimpleState(length(object_versions.val_dump)) AS size_bytes,
    minSimpleState(object_versions.created_at) AS created_at,
    maxSimpleState(object_versions.created_at) AS updated_at
FROM object_versions
GROUP BY
    object_versions.project_id,
    object_versions.kind,
    object_versions.object_id,
    object_versions.digest;