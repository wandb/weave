import re

from weave.trace_server.calls_query_builder import CallsQuery
from weave.trace_server.orm import ParamBuilder


def test_query_baseline() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    assert_sql(
        cq,
        """
        SELECT calls_merged.id AS id
        FROM calls_merged
        WHERE project_id = {pb_0:String}
        GROUPBY(project_id,id)
        HAVING (
            any(calls_merged.deleted_at) IS NULL
        )
        """,
        {"pb_0": "project"},
    )


def test_query_with_simple_columns() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("started_at")
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id,
            any(calls_merged.started_at) AS started_at
        FROM calls_merged
        WHERE project_id = {pb_0:String}
        GROUPBY(project_id,id)
        HAVING (
            any(calls_merged.deleted_at) IS NULL
        )
        """,
        {"pb_0": "project"},
    )


def assert_sql(cq: CallsQuery, exp_query, exp_params):
    pb = ParamBuilder("pb")
    query = cq.as_sql(pb)
    params = pb.get_params()

    assert exp_params == params

    expected_no_whitespace = re.sub(r"\s+", "", exp_query)
    found_no_whitespace = re.sub(r"\s+", "", query)

    assert expected_no_whitespace == found_no_whitespace
