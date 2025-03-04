ALTER TABLE files_stats_view MODIFY QUERY
SELECT
    files.project_id,
    files.digest,
    files.chunk_index,
    anySimpleState(files.n_chunks) as n_chunks,
    anySimpleState(files.name) as name,
    anySimpleState(length(files.val_bytes)) AS size_bytes,
    minSimpleState(files.created_at) AS created_at,
    maxSimpleState(files.created_at) AS updated_at
FROM files
GROUP BY
    files.project_id,
    files.digest,
    files.chunk_index;

ALTER TABLE files_stats DROP COLUMN file_storage_uri;

ALTER TABLE files DROP COLUMN bytes_stored;
ALTER TABLE files DROP COLUMN file_storage_uri;
