"""Query builder utilities for the files and files_stats tables."""

from weave.trace_server.orm import ParamBuilder


def make_file_content_read_query(
    project_id: str,
    digest: str,
    pb: ParamBuilder,
) -> str:
    """Generate a query to read file chunks for a given digest.

    The inner subquery deduplicates chunks by (project_id, digest, chunk_index)
    using row_number() so that only the most recently inserted chunk per index
    is returned from the ReplacingMergeTree parts.
    """
    project_id_param = pb.add_param(project_id)
    digest_param = pb.add_param(digest)

    return f"""
    SELECT n_chunks, val_bytes, file_storage_uri
    FROM (
        SELECT *
        FROM (
                SELECT *,
                    row_number() OVER (PARTITION BY project_id, digest, chunk_index) AS rn
                FROM files
                WHERE project_id = {{{project_id_param}: String}} AND digest = {{{digest_param}: String}}
            )
        WHERE rn = 1
        ORDER BY project_id, digest, chunk_index
    )
    WHERE project_id = {{{project_id_param}: String}} AND digest = {{{digest_param}: String}}
    """


def make_files_stats_query(
    project_id: str,
    pb: ParamBuilder,
) -> str:
    """Generate a query that returns the total file storage size for a project."""
    project_id_param = pb.add_param(project_id)
    return f"""
    SELECT sum(size_bytes) as total_size_bytes
    FROM files_stats
    WHERE project_id = {{{project_id_param}: String}}
    """
