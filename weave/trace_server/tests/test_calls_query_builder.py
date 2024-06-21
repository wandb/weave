import re

from weave.trace_server.calls_query_builder import CallsQuery
from weave.trace_server.orm import ParamBuilder


def test_basic_query() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    assert_sql(
        cq,
        """
        SELECT calls_merged.id AS id
        FROM calls_merged
        WHERE project_id = {pb_0:String}
        GROUPBY(project_id,id)
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
