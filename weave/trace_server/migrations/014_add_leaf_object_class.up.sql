ALTER TABLE object_versions
    ADD COLUMN leaf_object_class Nullable(String) DEFAULT NULL;