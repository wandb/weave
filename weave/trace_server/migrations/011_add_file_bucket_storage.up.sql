ALTER TABLE files ADD COLUMN bytes_stored Nullable(UInt32);
ALTER TABLE files ADD COLUMN file_storage_uri Nullable(String);

ALTER TABLE files_stats ADD COLUMN file_storage_uri Nullable(String);

ALTER TABLE files_stats_view MODIFY QUERY
SELECT
    files.project_id,
    files.digest,
    files.chunk_index,
    anySimpleState(files.n_chunks) as n_chunks,
    anySimpleState(files.name) as name,
    anySimpleState(length(files.val_bytes) + files.bytes_stored) AS size_bytes,
    anySimpleState(files.file_storage_uri) AS file_storage_uri,
    minSimpleState(files.created_at) AS created_at,
    maxSimpleState(files.created_at) AS updated_at
FROM files
GROUP BY
    files.project_id,
    files.digest,
    files.chunk_index;