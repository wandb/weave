import re

import sqlparse

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder import CallsQuery, HardCodedFilter
from weave.trace_server.interface import query as tsi_query
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
        GROUP BY (project_id,id)
        HAVING (
            any(calls_merged.deleted_at) IS NULL
        )
        """,
        {"pb_0": "project"},
    )


def test_query_light_column() -> None:
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
        GROUP BY (project_id,id)
        HAVING (
            any(calls_merged.deleted_at) IS NULL
        )
        """,
        {"pb_0": "project"},
    )


def test_query_heavy_column() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        WHERE project_id = {pb_0:String}
        GROUP BY (project_id,id)
        HAVING (
            any(calls_merged.deleted_at) IS NULL
        )
        """,
        {"pb_0": "project"},
    )


def test_query_heavy_column_simple_filter() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi._CallsFilter(
                op_names=["a", "b"],
            )
        )
    )
    assert_sql(
        cq,
        """
        WITH filtered_calls AS (
            SELECT
                calls_merged.id AS id
            FROM calls_merged
            WHERE project_id = {pb_1:String}
            GROUP BY (project_id,id)
            HAVING (
                ((any(calls_merged.deleted_at) IS NULL))
            AND
                (any(calls_merged.op_name) IN {pb_0:Array(String)})
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        WHERE
            project_id = {pb_2:String}
        AND
            (id IN filtered_calls)
        GROUP BY (project_id,id)
        """,
        {"pb_0": ["a", "b"], "pb_1": "project", "pb_2": "project"},
    )


def test_query_heavy_column_simple_filter_with_order() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_order("started_at", "desc")
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi._CallsFilter(
                op_names=["a", "b"],
            )
        )
    )
    assert_sql(
        cq,
        """
        WITH filtered_calls AS (
            SELECT
                calls_merged.id AS id
            FROM calls_merged
            WHERE project_id = {pb_1:String}
            GROUP BY (project_id,id)
            HAVING (
                ((any(calls_merged.deleted_at) IS NULL))
            AND
                (any(calls_merged.op_name) IN {pb_0:Array(String)})
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        WHERE
            project_id = {pb_2:String}
        AND
            (id IN filtered_calls)
        GROUP BY (project_id,id)
        ORDER BY any(calls_merged.started_at) DESC
        """,
        {"pb_0": ["a", "b"], "pb_1": "project", "pb_2": "project"},
    )


def test_query_heavy_column_simple_filter_with_order_and_limit() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_order("started_at", "desc")
    cq.set_limit(10)
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi._CallsFilter(
                op_names=["a", "b"],
            )
        )
    )
    assert_sql(
        cq,
        """
        WITH filtered_calls AS (
            SELECT
                calls_merged.id AS id
            FROM calls_merged
            WHERE project_id = {pb_1:String}
            GROUP BY (project_id,id)
            HAVING (
                ((any(calls_merged.deleted_at) IS NULL))
            AND
                (any(calls_merged.op_name) IN {pb_0:Array(String)})
            )
            ORDER BY any(calls_merged.started_at) DESC
            LIMIT 10
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        WHERE
            project_id = {pb_2:String}
        AND
            (id IN filtered_calls)
        GROUP BY (project_id,id)
        ORDER BY any(calls_merged.started_at) DESC
        """,
        {"pb_0": ["a", "b"], "pb_1": "project", "pb_2": "project"},
    )


def test_query_heavy_column_simple_filter_with_order_and_limit_and_mixed_query_conditions() -> (
    None
):
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_order("started_at", "desc")
    cq.set_limit(10)
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi._CallsFilter(
                op_names=["a", "b"],
            )
        )
    )
    cq.add_condition(
        tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    {
                        "$eq": [
                            {"$getField": "inputs.param.val"},
                            {"$literal": "hello"},
                        ]
                    },  # <-- heavy condition
                    {
                        "$eq": [{"$getField": "wb_user_id"}, {"$literal": "my_user_id"}]
                    },  # <-- light condition
                ]
            }
        )
    )
    assert_sql(
        cq,
        """
        WITH filtered_calls AS (
            SELECT
                calls_merged.id AS id
            FROM calls_merged
            WHERE project_id = {pb_2:String}
            GROUP BY (project_id,id)
            HAVING (
                ((any(calls_merged.wb_user_id) = {pb_0:String}))
            AND
                ((any(calls_merged.deleted_at) IS NULL))
            AND
                (any(calls_merged.op_name) IN {pb_1:Array(String)})
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        WHERE
            project_id = {pb_5:String}
        AND
            (id IN filtered_calls)
        GROUP BY (project_id,id)
        HAVING (
            JSON_VALUE(any(calls_merged.inputs_dump), {pb_3:String}) = {pb_4:String}
        )
        ORDER BY any(calls_merged.started_at) DESC
        LIMIT 10
        """,
        {
            "pb_0": "my_user_id",
            "pb_1": ["a", "b"],
            "pb_2": "project",
            "pb_3": '$."param"."val"',
            "pb_4": "hello",
            "pb_5": "project",
        },
    )


def assert_sql(cq: CallsQuery, exp_query, exp_params):
    pb = ParamBuilder("pb")
    query = cq.as_sql(pb)
    params = pb.get_params()

    assert exp_params == params

    exp_formatted = sqlparse.format(exp_query, reindent=True)
    found_formatted = sqlparse.format(query, reindent=True)

    assert exp_formatted == found_formatted
