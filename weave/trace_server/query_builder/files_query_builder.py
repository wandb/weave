"""Query builder utilities for the files and files_stats tables."""

from weave.trace_server.orm import ParamBuilder


def make_file_content_read_query(
    project_id: str,
    digest: str,
    pb: ParamBuilder,
) -> str:
    """Generate a query to read file chunks for a given digest.

    The inner window deduplicates chunks by (project_id, digest, chunk_index)
    across unmerged ReplacingMergeTree parts. The `ORDER BY file_storage_uri
    IS NULL DESC` makes the pick deterministic: when an inline-CH row and a
    bucket-URI row coexist at the same PK (e.g. bucket write succeeded for
    one writer, fell back to inline CH for another), the inline-CH row wins.
    File contents are content-addressable by digest, so either row carries
    the correct bytes; preferring inline-CH avoids a hard read failure when
    the bucket is unreachable.
    """
    project_id_param = pb.add_param(project_id)
    digest_param = pb.add_param(digest)

    return f"""
    SELECT n_chunks, val_bytes, file_storage_uri
    FROM (
        SELECT *
        FROM (
                SELECT *,
                    row_number() OVER (
                        PARTITION BY project_id, digest, chunk_index
                        ORDER BY file_storage_uri IS NULL DESC
                    ) AS rn
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
