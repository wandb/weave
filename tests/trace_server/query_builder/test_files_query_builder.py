import sqlparse

from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.files_query_builder import (
    make_file_content_read_query,
    make_files_stats_query,
)


def assert_sql(
    expected_query: str, expected_params: dict, query: str, params: dict
) -> None:
    expected_formatted = sqlparse.format(expected_query, reindent=True)
    found_formatted = sqlparse.format(query, reindent=True)

    assert expected_formatted == found_formatted, (
        f"\nExpected:\n{expected_formatted}\n\nGot:\n{found_formatted}"
    )
    assert expected_params == params, (
        f"\nExpected params: {expected_params}\n\nGot params: {params}"
    )


def test_make_file_content_read_query() -> None:
    pb = ParamBuilder("pb")
    query = make_file_content_read_query(
        project_id="project",
        digest="abc123",
        pb=pb,
    )
    params = pb.get_params()

    expected_query = """
    SELECT n_chunks, val_bytes, file_storage_uri
    FROM (
        SELECT *
        FROM (
                SELECT *,
                    row_number() OVER (PARTITION BY project_id, digest, chunk_index) AS rn
                FROM files
                WHERE project_id = {pb_0: String} AND digest = {pb_1: String}
            )
        WHERE rn = 1
        ORDER BY project_id, digest, chunk_index
    )
    WHERE project_id = {pb_0: String} AND digest = {pb_1: String}
    """

    expected_params = {
        "pb_0": "project",
        "pb_1": "abc123",
    }

    assert_sql(expected_query, expected_params, query, params)


def test_make_files_stats_query() -> None:
    pb = ParamBuilder("pb")
    query = make_files_stats_query(project_id="project", pb=pb)
    params = pb.get_params()

    expected_query = """
    SELECT sum(size_bytes) as total_size_bytes
    FROM files_stats
    WHERE project_id = {pb_0: String}
    """

    expected_params = {"pb_0": "project"}

    assert_sql(expected_query, expected_params, query, params)
