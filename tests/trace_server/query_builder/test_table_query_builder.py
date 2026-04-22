import sqlparse

from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.table_query_builder import (
    make_table_row_digests_query,
    make_table_stats_basic_query,
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


def test_make_table_row_digests_query() -> None:
    pb = ParamBuilder("pb")
    query = make_table_row_digests_query(
        project_id="project",
        digest="base-digest",
        pb=pb,
    )
    params = pb.get_params()

    expected_query = """
    SELECT *
    FROM (
            SELECT *,
                row_number() OVER (PARTITION BY project_id, digest) AS rn
            FROM tables
            WHERE project_id = {pb_0: String} AND digest = {pb_1: String}
        )
    WHERE rn = 1
    ORDER BY project_id, digest
    """

    expected_params = {
        "pb_0": "project",
        "pb_1": "base-digest",
    }

    assert_sql(expected_query, expected_params, query, params)


def test_make_table_stats_basic_query() -> None:
    pb = ParamBuilder("pb")
    query = make_table_stats_basic_query(
        project_id="project",
        table_digests=["d1", "d2"],
        pb=pb,
    )
    params = pb.get_params()

    expected_query = """
    SELECT digest, any(length(row_digests))
    FROM tables
    WHERE project_id = {pb_0: String} AND digest IN {pb_1: Array(String)}
    GROUP BY digest
    """

    expected_params = {
        "pb_0": "project",
        "pb_1": ["d1", "d2"],
    }

    assert_sql(expected_query, expected_params, query, params)
