CREATE TABLE objects
(
    project_id String,
    name String,
    created_at DateTime64 DEFAULT now64(),
    type String,
    refs Array(String),
    val String,
    digest String
) 
ENGINE = ReplacingMergeTree() 
ORDER BY (project_id, type, name, digest);

CREATE VIEW objects_deduped AS
SELECT
    project_id,
    name,
    created_at,
    type,
    refs,
    val,
    digest,
    if (type = 'Op', 1, 0) AS is_op,
    row_number() OVER (PARTITION BY project_id, type, name ORDER BY created_at ASC) AS _version_index_plus_1,
    _version_index_plus_1 - 1 AS version_index,
    count(*) OVER (PARTITION BY project_id, type, name) as version_count,
    if(_version_index_plus_1 = version_count, 1, 0) AS is_latest
FROM (
    SELECT *,
           row_number() OVER (PARTITION BY project_id, type, name, digest ORDER BY created_at ASC) AS rn
    FROM objects
) WHERE rn = 1
WINDOW w AS (PARTITION BY project_id, type, name ORDER BY created_at ASC)
ORDER BY project_id, type, name, created_at;

CREATE TABLE table_rows
(
    project_id String,
    digest String,
    val String,
) 
ENGINE = ReplacingMergeTree() 
ORDER BY (project_id, digest);

CREATE VIEW table_rows_deduped AS
SELECT *
FROM (
    SELECT *,
           row_number() OVER (PARTITION BY project_id, digest) AS rn
    FROM table_rows
) WHERE rn = 1
ORDER BY project_id, digest;

CREATE TABLE tables
(
    project_id String,
    digest String,
    row_digests Array(String),
) 
ENGINE = ReplacingMergeTree() 
ORDER BY (project_id, digest);

CREATE VIEW tables_deduped AS
SELECT *
FROM (
    SELECT *,
           row_number() OVER (PARTITION BY project_id, digest) AS rn
    FROM tables
) WHERE rn = 1
ORDER BY project_id, digest;


CREATE TABLE files
(
    project_id String,
    digest String,
    chunk_index UInt32,
    n_chunks UInt32,
    name String,
    val String,
) 
ENGINE = ReplacingMergeTree() 
ORDER BY (project_id, digest, chunk_index);

CREATE VIEW files_deduped AS
SELECT *
FROM (
    SELECT *,
           row_number() OVER (PARTITION BY project_id, digest, chunk_index) AS rn
    FROM files
) WHERE rn = 1
ORDER BY project_id, digest, chunk_index;
