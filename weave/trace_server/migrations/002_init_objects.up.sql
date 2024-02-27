CREATE TABLE objects_raw (
    entity String,
    project String,
    is_op UInt8,
    name String,
    version_hash String,
    created_datetime DateTime64(3),
    type_dict_dump String,
    bytes_file_map Map(String, String),
    metadata_dict_dump String,
    db_row_created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree
ORDER BY (entity, project, is_op, name, version_hash);
CREATE TABLE objects_deduplicated (
    entity String,
    project String,
    is_op UInt8,
    name String,
    version_hash String,
    created_datetime SimpleAggregateFunction(min, DateTime64(3)),
    type_dict_dump SimpleAggregateFunction(any, String),
    bytes_file_map SimpleAggregateFunction(any, Map(String, String)),
    # Note: if we ever want to support updates, this needs to be moved to a more robust handling
    metadata_dict_dump SimpleAggregateFunction(any, String),
) ENGINE = AggregatingMergeTree
ORDER BY (entity, project, is_op, name, version_hash);
CREATE MATERIALIZED VIEW objects_deduplicated_view TO objects_deduplicated AS
SELECT entity,
    project,
    is_op,
    name,
    version_hash,
    minSimpleState(created_datetime) as created_datetime,
    anySimpleState(type_dict_dump) as type_dict_dump,
    anySimpleState(bytes_file_map) as bytes_file_map,
    anySimpleState(metadata_dict_dump) as metadata_dict_dump
FROM objects_raw
GROUP BY entity,
    project,
    is_op,
    name,
    version_hash;
CREATE VIEW objects_versioned AS
SELECT entity,
    project,
    is_op,
    name,
    version_hash,
    min(objects_deduplicated.created_datetime) as created_datetime,
    any(type_dict_dump) as type_dict_dump,
    any(bytes_file_map) as bytes_file_map,
    any(metadata_dict_dump) as metadata_dict_dump,
    row_number() OVER w1 as version_index,
    1 == count(*) OVER w1 as is_latest
FROM objects_deduplicated
GROUP BY entity,
    project,
    is_op,
    name,
    version_hash WINDOW w1 AS (
        PARTITION BY entity,
        project,
        is_op,
        name
        ORDER BY min(objects_deduplicated.created_datetime) ASC Rows BETWEEN CURRENT ROW
            AND 1 FOLLOWING
    );
