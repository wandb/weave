CREATE TABLE objects (
    project_id String,
    name String,
    created_at DateTime64 DEFAULT now64(),
    kind Enum('op', 'object'),
    base_object_class String NULL,
    refs Array(String),
    val String,
    digest String
) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, kind, name, digest);
CREATE VIEW objects_deduped AS
SELECT project_id,
    name,
    created_at,
    kind,
    base_object_class,
    refs,
    val,
    digest,
    if (kind = 'op', 1, 0) AS is_op,
    row_number() OVER (
        PARTITION BY project_id,
        kind,
        name
        ORDER BY created_at ASC
    ) AS _version_index_plus_1,
    _version_index_plus_1 - 1 AS version_index,
    count(*) OVER (PARTITION BY project_id, kind, name) as version_count,
    if(_version_index_plus_1 = version_count, 1, 0) AS is_latest
FROM (
        SELECT *,
            row_number() OVER (
                PARTITION BY project_id,
                kind,
                name,
                digest
                ORDER BY created_at ASC
            ) AS rn
        FROM objects
    )
WHERE rn = 1 WINDOW w AS (
        PARTITION BY project_id,
        kind,
        name
        ORDER BY created_at ASC
    )
ORDER BY project_id,
    kind,
    name,
    created_at;
CREATE TABLE table_rows (
    project_id String,
    digest String,
    val String,
) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, digest);
CREATE VIEW table_rows_deduped AS
SELECT *
FROM (
        SELECT *,
            row_number() OVER (PARTITION BY project_id, digest) AS rn
        FROM table_rows
    )
WHERE rn = 1
ORDER BY project_id,
    digest;
CREATE TABLE tables (
    project_id String,
    digest String,
    row_digests Array(String),
) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, digest);
CREATE VIEW tables_deduped AS
SELECT *
FROM (
        SELECT *,
            row_number() OVER (PARTITION BY project_id, digest) AS rn
        FROM tables
    )
WHERE rn = 1
ORDER BY project_id,
    digest;
CREATE TABLE files (
    project_id String,
    digest String,
    chunk_index UInt32,
    n_chunks UInt32,
    name String,
    val String,
) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, digest, chunk_index);
CREATE VIEW files_deduped AS
SELECT *
FROM (
        SELECT *,
            row_number() OVER (PARTITION BY project_id, digest, chunk_index) AS rn
        FROM files
    )
WHERE rn = 1
ORDER BY project_id,
    digest,
    chunk_index;
