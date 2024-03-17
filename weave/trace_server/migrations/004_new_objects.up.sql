CREATE TABLE objects
(
    entity String,
    project String,
    name String,
    created_at DateTime64 DEFAULT now64(),
    type String,
    refs Array(String),
    val String,
    digest String
) 
ENGINE = MergeTree() 
ORDER BY (entity, project, type, name, created_at);

CREATE VIEW objects_deduped AS
SELECT
    entity,
    project,
    name,
    created_at,
    type,
    refs,
    val,
    digest,
    if (type = 'OpDef', 1, 0) AS is_op,
    row_number() OVER (PARTITION BY entity, project, type, name ORDER BY created_at ASC) AS _version_index_plus_1,
    _version_index_plus_1 - 1 AS version_index,
    count(*) OVER (PARTITION BY entity, project, type, name) as version_count,
    if(_version_index_plus_1 = version_count, 1, 0) AS is_latest
FROM (
    SELECT *,
           row_number() OVER (PARTITION BY entity, project, type, name, digest ORDER BY created_at ASC) AS rn
    FROM objects
) WHERE rn = 1
WINDOW w AS (PARTITION BY entity, project, type, name ORDER BY created_at ASC)
ORDER BY entity, project, type, name, created_at;

CREATE TABLE table_rows
(
    entity String,
    project String,
    digest String,
    val String,
) 
ENGINE = MergeTree() 
ORDER BY (entity, project, digest);

CREATE TABLE tables
(
    entity String,
    project String,
    digest String,
    row_digests Array(String),
) 
ENGINE = MergeTree() 
ORDER BY (entity, project, digest);
