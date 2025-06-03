ALTER TABLE object_versions
    ADD COLUMN leaf_object_class Nullable(String) DEFAULT NULL;

ALTER TABLE object_versions_stats
    ADD COLUMN leaf_object_class SimpleAggregateFunction(any, Nullable(String));