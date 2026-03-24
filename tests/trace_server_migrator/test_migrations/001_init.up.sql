CREATE TABLE test_tbl (
    id String,
    project_id String
) ENGINE = MergeTree
ORDER BY (project_id, id);
