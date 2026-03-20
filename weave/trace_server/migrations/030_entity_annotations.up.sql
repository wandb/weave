CREATE TABLE IF NOT EXISTS entity_annotations (
    project_id          String,
    entity_type         LowCardinality(String),
    entity_id           String,
    namespace           LowCardinality(String),
    key                 LowCardinality(String),

    string_value        String DEFAULT '',
    float_value         Float64 DEFAULT 0,
    int_value           Int64 DEFAULT 0,
    json_value          String DEFAULT '',
    value_type          Enum8('string'=1,'float'=2,'int'=3,'json'=4),

    source              LowCardinality(String) DEFAULT '',
    source_id           String DEFAULT '',
    updated_at          DateTime64(3) DEFAULT now64(3),

    deleted_at          DateTime64(3) DEFAULT toDateTime64(0, 3),

    INDEX idx_entity    entity_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_key       key TYPE set(200) GRANULARITY 4,
    INDEX idx_ns        namespace TYPE set(20) GRANULARITY 4,
    INDEX idx_sval      string_value TYPE bloom_filter(0.01) GRANULARITY 1
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (project_id, entity_type, entity_id, namespace, key)
SETTINGS do_not_merge_across_partitions_select_final = 1;
