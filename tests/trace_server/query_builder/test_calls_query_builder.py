import pytest
import sqlparse

from tests.trace_server.query_builder.utils import assert_sql, assert_stats_sql
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import (
    AggregatedDataSizeField,
    CallsQuery,
    HardCodedFilter,
    _is_minimal_filter,
    build_calls_complete_delete_query,
    build_calls_complete_update_end_query,
    build_calls_complete_update_query,
)
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable


@pytest.mark.parametrize(
    ("read_table", "expected_table"),
    [
        (ReadTable.CALLS_MERGED, "calls_merged"),
        (ReadTable.CALLS_COMPLETE, "calls_complete"),
    ],
)
def test_query_baseline(read_table: ReadTable, expected_table: str) -> None:
    """Test baseline query generates correct table references and full query shape."""
    cq = CallsQuery(project_id="project", read_table=read_table)
    cq.add_field("id")

    if read_table == ReadTable.CALLS_MERGED:
        expected_query = f"""
            SELECT {expected_table}.id AS id
            FROM {expected_table}
            PREWHERE {expected_table}.project_id = {{pb_0:String}}
            GROUP BY ({expected_table}.project_id, {expected_table}.id)
            HAVING (
                ((
                    any({expected_table}.deleted_at) IS NULL
                ))
                AND
                ((
                   NOT ((
                      any({expected_table}.started_at) IS NULL
                   ))
                ))
            )
        """
    else:
        expected_query = f"""
            SELECT {expected_table}.id AS id
            FROM {expected_table}
            PREWHERE {expected_table}.project_id = {{pb_0:String}}
            WHERE 1
              AND (
                ((
                    {expected_table}.deleted_at IS NULL
                ))
                AND
                ((
                   NOT ((
                      {expected_table}.started_at IS NULL
                   ))
                ))
            )
        """
    assert_sql(cq, expected_query, {"pb_0": "project"})


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
        PREWHERE calls_merged.project_id = {pb_0:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((
                any(calls_merged.deleted_at) IS NULL
            ))
            AND
            ((
               NOT ((
                  any(calls_merged.started_at) IS NULL
               ))
            ))
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
        PREWHERE calls_merged.project_id = {pb_0:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((
                any(calls_merged.deleted_at) IS NULL
            ))
            AND
            ((
               NOT ((
                  any(calls_merged.started_at) IS NULL
               ))
            ))
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
            filter=tsi.CallsFilter(
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
            PREWHERE calls_merged.project_id = {pb_1:String}
            WHERE ((calls_merged.op_name IN {pb_0:Array(String)})
                    OR (calls_merged.op_name IS NULL))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_1:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        """,
        {"pb_0": ["a", "b"], "pb_1": "project"},
    )


def test_query_no_order() -> None:
    """Test that omitting add_order produces no ORDER BY clause.

    This corresponds to passing sort_by=[] at the API level, which explicitly
    disables sorting for performance.
    """
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("started_at")
    # No add_order calls — should produce no ORDER BY
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id,
            any(calls_merged.started_at) AS started_at
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_0:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((
                any(calls_merged.deleted_at) IS NULL
            ))
            AND
            ((
               NOT ((
                  any(calls_merged.started_at) IS NULL
               ))
            ))
        )
        """,
        {"pb_0": "project"},
    )


def test_query_no_order_with_limit() -> None:
    """Test no ORDER BY with LIMIT still works.

    This is the primary performance case: getting a batch of rows without
    paying for sorting.
    """
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("started_at")
    cq.set_limit(100)
    # No add_order calls — should produce LIMIT but no ORDER BY
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id,
            any(calls_merged.started_at) AS started_at
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_0:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((
                any(calls_merged.deleted_at) IS NULL
            ))
            AND
            ((
               NOT ((
                  any(calls_merged.started_at) IS NULL
               ))
            ))
        )
        LIMIT 100
        """,
        {"pb_0": "project"},
    )


def test_query_no_order_with_filter() -> None:
    """Test no ORDER BY with filter applied.

    Verifies that the filtered_calls CTE also has no ORDER BY when no
    sorting is specified.
    """
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
                op_names=["a", "b"],
            )
        )
    )
    # No add_order calls — neither CTE nor main query should have ORDER BY
    assert_sql(
        cq,
        """
        WITH filtered_calls AS (
            SELECT
                calls_merged.id AS id
            FROM calls_merged
            PREWHERE calls_merged.project_id = {pb_1:String}
            WHERE ((calls_merged.op_name IN {pb_0:Array(String)})
                    OR (calls_merged.op_name IS NULL))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_1:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        """,
        {"pb_0": ["a", "b"], "pb_1": "project"},
    )


def test_query_heavy_column_simple_filter_with_order() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_order("started_at", "desc")
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
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
            PREWHERE calls_merged.project_id = {pb_1:String}
            WHERE ((calls_merged.op_name IN {pb_0:Array(String)})
                    OR (calls_merged.op_name IS NULL))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
            ORDER BY any(calls_merged.started_at) DESC
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_1:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        ORDER BY any(calls_merged.started_at) DESC
        """,
        {"pb_0": ["a", "b"], "pb_1": "project"},
    )


def test_query_heavy_column_simple_filter_with_order_and_limit() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_order("started_at", "desc")
    cq.set_limit(10)
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
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
            PREWHERE calls_merged.project_id = {pb_1:String}
            WHERE ((calls_merged.op_name IN {pb_0:Array(String)})
                    OR (calls_merged.op_name IS NULL))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((any(calls_merged.deleted_at) IS NULL))
            AND
                ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
            ORDER BY any(calls_merged.started_at) DESC
            LIMIT 10
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_1:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        ORDER BY any(calls_merged.started_at) DESC
        """,
        {"pb_0": ["a", "b"], "pb_1": "project"},
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
            filter=tsi.CallsFilter(
                op_names=["a", "b"],
                trace_ids=["111111111111"],
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
                        "$eq": [
                            {"$getField": "inputs.param.bool"},
                            {"$literal": "true"},
                        ]
                    },  # <-- heavy condition with boolean literal
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
            PREWHERE calls_merged.project_id = {pb_9:String}
            WHERE ((calls_merged.op_name IN {pb_5:Array(String)})
                    OR (calls_merged.op_name IS NULL))
                AND (calls_merged.trace_id = {pb_6:String}
                    OR calls_merged.trace_id IS NULL)
                AND ((calls_merged.inputs_dump LIKE {pb_7:String} OR calls_merged.inputs_dump IS NULL)
                    AND (calls_merged.inputs_dump LIKE {pb_8:String} OR calls_merged.inputs_dump IS NULL))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                                    ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}), 'null'), '') = {pb_1:String}))
                    AND
                    ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_2:String}), 'null'), '') = {pb_3:String}))
                AND
                ((any(calls_merged.wb_user_id) = {pb_4:String}))
                AND
                ((any(calls_merged.deleted_at) IS NULL))
                AND
                ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
            ORDER BY any(calls_merged.started_at) DESC
            LIMIT 10
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_9:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        ORDER BY any(calls_merged.started_at) DESC
        """,
        {
            "pb_0": '$."param"."val"',
            "pb_1": "hello",
            "pb_2": '$."param"."bool"',
            "pb_3": "true",
            "pb_4": "my_user_id",
            "pb_5": ["a", "b"],
            "pb_6": "111111111111",
            "pb_7": '%"hello"%',
            "pb_8": "%true%",
            "pb_9": "project",
        },
    )


def test_query_with_simple_feedback_sort() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_order("feedback.[wandb.runnable.my_op].payload.output.expected", "desc")
    assert_sql(
        cq,
        """
            SELECT
                calls_merged.id AS id
            FROM
                calls_merged
            LEFT JOIN (
                SELECT * FROM feedback WHERE feedback.project_id = {pb_4:String}
            ) AS feedback ON (
                feedback.weave_ref = concat('weave-trace-internal:///',
                {pb_4:String},
                '/call/',
                calls_merged.id))
            PREWHERE
                calls_merged.project_id = {pb_4:String}
            GROUP BY
                (calls_merged.project_id,
                calls_merged.id)
            HAVING
                (((any(calls_merged.deleted_at) IS NULL))
                    AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
            ORDER BY
                (NOT (JSONType(anyIf(feedback.payload_dump,
                feedback.feedback_type = {pb_0:String}),
                {pb_1:String},
                {pb_2:String}) = 'Null'
                    OR JSONType(anyIf(feedback.payload_dump,
                    feedback.feedback_type = {pb_0:String}),
                    {pb_1:String},
                    {pb_2:String}) IS NULL)) desc,
                toFloat64OrNull(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
                feedback.feedback_type = {pb_0:String}),
                {pb_3:String}), 'null'), '')) DESC,
                toString(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
                feedback.feedback_type = {pb_0:String}),
                {pb_3:String}), 'null'), '')) DESC
            """,
        {
            "pb_0": "wandb.runnable.my_op",
            "pb_1": "output",
            "pb_2": "expected",
            "pb_3": '$."output"."expected"',
            "pb_4": "project",
        },
    )


def test_query_with_simple_feedback_sort_with_op_name() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter={"op_names": ["weave-trace-internal:///project/op/my_op:1234567890"]}
        )
    )
    cq.add_order("feedback.[wandb.runnable.my_op].payload.output.expected", "desc")
    assert_sql(
        cq,
        """
        WITH filtered_calls AS
        (
        SELECT
            calls_merged.id AS id
        FROM
            calls_merged
                    LEFT JOIN (
                SELECT * FROM feedback WHERE feedback.project_id = {pb_5:String}
            ) AS feedback ON (
                feedback.weave_ref = concat('weave-trace-internal:///',
                {pb_5:String},
                '/call/',
                calls_merged.id))
            PREWHERE
                calls_merged.project_id = {pb_5:String}
            WHERE ((calls_merged.op_name IN {pb_0:Array(String)})
                    OR (calls_merged.op_name IS NULL))
        GROUP BY
            (calls_merged.project_id,
            calls_merged.id)
        HAVING
            (((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        ORDER BY
            (NOT (JSONType(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_1:String}),
            {pb_2:String},
            {pb_3:String}) = 'Null'
                OR JSONType(anyIf(feedback.payload_dump,
                feedback.feedback_type = {pb_1:String}),
                {pb_2:String},
                {pb_3:String}) IS NULL)) desc,
            toFloat64OrNull(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_1:String}),
            {pb_4:String}), 'null'), '')) DESC,
            toString(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_1:String}),
            {pb_4:String}), 'null'), '')) DESC
        )
        SELECT
            calls_merged.id AS id
        FROM
            calls_merged
                    LEFT JOIN (
                SELECT * FROM feedback WHERE feedback.project_id = {pb_5:String}
            ) AS feedback ON (
                feedback.weave_ref = concat('weave-trace-internal:///',
                {pb_5:String},
                '/call/',
                calls_merged.id))
            PREWHERE
                calls_merged.project_id = {pb_5:String}
            WHERE (calls_merged.id IN filtered_calls)
        GROUP BY
            (calls_merged.project_id,
            calls_merged.id)
        ORDER BY
            (NOT (JSONType(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_1:String}),
            {pb_2:String},
            {pb_3:String}) = 'Null'
                OR JSONType(anyIf(feedback.payload_dump,
                feedback.feedback_type = {pb_1:String}),
                {pb_2:String},
                {pb_3:String}) IS NULL)) desc,
            toFloat64OrNull(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_1:String}),
            {pb_4:String}), 'null'), '')) DESC,
            toString(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_1:String}),
            {pb_4:String}), 'null'), '')) DESC
        """,
        {
            "pb_0": ["weave-trace-internal:///project/op/my_op:1234567890"],
            "pb_1": "wandb.runnable.my_op",
            "pb_2": "output",
            "pb_3": "expected",
            "pb_4": '$."output"."expected"',
            "pb_5": "project",
        },
    )


def test_query_with_simple_feedback_filter() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {
                        "$getField": "feedback.[wandb.runnable.my_op].payload.output.expected"
                    },
                    {
                        "$getField": "feedback.[wandb.runnable.my_op].payload.output.found"
                    },
                ]
            }
        )
    )
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM
            calls_merged
                    LEFT JOIN (
                SELECT * FROM feedback WHERE feedback.project_id = {pb_3:String}
            ) AS feedback ON (
            feedback.weave_ref = concat('weave-trace-internal:///',
            {pb_3:String},
            '/call/',
            calls_merged.id))
        PREWHERE
            calls_merged.project_id = {pb_3:String}
        GROUP BY
            (calls_merged.project_id,
            calls_merged.id)
        HAVING
            (((coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_0:String}),
            {pb_1:String}), 'null'), '') > coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_0:String}),
            {pb_2:String}), 'null'), '')))
                AND ((any(calls_merged.deleted_at) IS NULL))
                    AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        """,
        {
            "pb_0": "wandb.runnable.my_op",
            "pb_1": '$."output"."expected"',
            "pb_2": '$."output"."found"',
            "pb_3": "project",
        },
    )


def test_query_with_simple_feedback_sort_and_filter() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {
                        "$getField": "feedback.[wandb.runnable.my_op].payload.output.expected"
                    },
                    {"$literal": "a"},
                ]
            }
        )
    )
    cq.add_order("feedback.[wandb.runnable.my_op].payload.output.score", "desc")
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM
            calls_merged
                    LEFT JOIN (
                SELECT * FROM feedback WHERE feedback.project_id = {pb_6:String}
            ) AS feedback ON (
            feedback.weave_ref = concat('weave-trace-internal:///',
            {pb_6:String},
            '/call/',
            calls_merged.id))
        PREWHERE
            calls_merged.project_id = {pb_6:String}
        GROUP BY
            (calls_merged.project_id,
            calls_merged.id)
        HAVING
            (((coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_0:String}),
            {pb_1:String}), 'null'), '') = {pb_2:String}))
                AND ((any(calls_merged.deleted_at) IS NULL))
                    AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        ORDER BY
            (NOT (JSONType(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_0:String}),
            {pb_3:String},
            {pb_4:String}) = 'Null'
                OR JSONType(anyIf(feedback.payload_dump,
                feedback.feedback_type = {pb_0:String}),
                {pb_3:String},
                {pb_4:String}) IS NULL)) desc,
            toFloat64OrNull(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_0:String}),
            {pb_5:String}), 'null'), '')) DESC,
            toString(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_0:String}),
            {pb_5:String}), 'null'), '')) DESC
        """,
        {
            "pb_0": "wandb.runnable.my_op",
            "pb_1": '$."output"."expected"',
            "pb_2": "a",
            "pb_3": "output",
            "pb_4": "score",
            "pb_5": '$."output"."score"',
            "pb_6": "project",
        },
    )


def test_query_with_simple_feedback_filter_calls_complete() -> None:
    """Test feedback filter on calls_complete table - should NOT use GROUP BY or aggregation."""
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {
                        "$getField": "feedback.[wandb.runnable.my_op].payload.output.expected"
                    },
                    {
                        "$getField": "feedback.[wandb.runnable.my_op].payload.output.found"
                    },
                ]
            }
        )
    )
    assert_sql(
        cq,
        """
        SELECT
            calls_complete.id AS id
        FROM
            calls_complete
                    LEFT JOIN (
                SELECT * FROM feedback WHERE feedback.project_id = {pb_3:String}
            ) AS feedback ON (
            feedback.weave_ref = concat('weave-trace-internal:///',
            {pb_3:String},
            '/call/',
            calls_complete.id))
        PREWHERE
            calls_complete.project_id = {pb_3:String}
        WHERE 1
        AND
            (((coalesce(nullIf(JSON_VALUE(CASE WHEN feedback.feedback_type = {pb_0:String} THEN feedback.payload_dump END,
            {pb_1:String}), 'null'), '') > coalesce(nullIf(JSON_VALUE(CASE WHEN feedback.feedback_type = {pb_0:String} THEN feedback.payload_dump END,
            {pb_2:String}), 'null'), '')))
                AND ((calls_complete.deleted_at IS NULL))
                    AND ((NOT ((calls_complete.started_at IS NULL)))))
        """,
        {
            "pb_0": "wandb.runnable.my_op",
            "pb_1": '$."output"."expected"',
            "pb_2": '$."output"."found"',
            "pb_3": "project",
        },
    )


def test_calls_query_multiple_select_columns() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_field("inputs")
    cq.add_field("inputs")
    cq.add_field("output")
    cq.add_field("output")
    cq.add_field("output")
    cq.add_field("output")
    cq.add_field("output")
    cq.add_field("output")
    cq.add_field("output")
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump,
            any(calls_merged.output_dump) AS output_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_0:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((
                any(calls_merged.deleted_at) IS NULL
            ))
            AND
            ((
               NOT ((
                  any(calls_merged.started_at) IS NULL
               ))
            ))
        )
        """,
        {"pb_0": "project"},
    )


def test_calls_query_with_predicate_filters() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
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
            PREWHERE calls_merged.project_id = {pb_4:String}
            WHERE ((calls_merged.inputs_dump LIKE {pb_3:String} OR calls_merged.inputs_dump IS NULL))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}), 'null'), '') = {pb_1:String}))
                AND ((any(calls_merged.wb_user_id) = {pb_2:String}))
                AND ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_4:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        """,
        {
            "pb_0": '$."param"."val"',
            "pb_1": "hello",
            "pb_2": "my_user_id",
            "pb_3": '%"hello"%',
            "pb_4": "project",
        },
    )


def test_query_with_summary_weave_status_sort() -> None:
    """Test sorting by summary.weave.status field."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("exception")
    cq.add_field("ended_at")
    cq.add_order("summary.weave.status", "asc")

    # Assert that the query orders by the computed status field
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id,
            any(calls_merged.exception) AS exception,
            any(calls_merged.ended_at) AS ended_at
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_5:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((
                any(calls_merged.deleted_at) IS NULL
            ))
            AND
            ((
               NOT ((
                  any(calls_merged.started_at) IS NULL
               ))
            ))
        )
        ORDER BY CASE
            WHEN any(calls_merged.exception) IS NOT NULL THEN {pb_1:String}
            WHEN IFNULL(
                toInt64OrNull(
                    coalesce(nullIf(JSON_VALUE(any(calls_merged.summary_dump), {pb_0:String}), 'null'), '')
                ),
                0
            ) > 0 THEN {pb_4:String}
            WHEN any(calls_merged.ended_at) IS NULL THEN {pb_2:String}
            ELSE {pb_3:String}
            END ASC
        """,
        {
            "pb_0": '$."status_counts"."error"',
            "pb_1": "error",
            "pb_2": "running",
            "pb_3": "success",
            "pb_4": "descendant_error",
            "pb_5": "project",
        },
    )


def test_query_with_summary_weave_status_sort_and_filter() -> None:
    """Test filtering and sorting by summary.weave.status field."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("exception")
    cq.add_field("ended_at")

    # Add a condition to filter for only successful calls
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {"$eq": [{"$getField": "summary.weave.status"}, {"$literal": "success"}]}
        )
    )

    # Sort by status descending
    cq.add_order("summary.weave.status", "desc")

    # Assert that the query includes both a filter and sort on the status field
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id,
            any(calls_merged.exception) AS exception,
            any(calls_merged.ended_at) AS ended_at
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_5:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((CASE
                WHEN any(calls_merged.exception) IS NOT NULL THEN {pb_1:String}
                WHEN IFNULL(toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.summary_dump), {pb_0:String}), 'null'), '')), 0) > 0 THEN {pb_4:String}
                WHEN any(calls_merged.ended_at) IS NULL THEN {pb_2:String}
                ELSE {pb_3:String}
            END = {pb_3:String}))
        AND ((any(calls_merged.deleted_at) IS NULL))
        AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        ORDER BY CASE
            WHEN any(calls_merged.exception) IS NOT NULL THEN {pb_1:String}
            WHEN IFNULL(toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.summary_dump), {pb_0:String}), 'null'), '')), 0) > 0 THEN {pb_4:String}
            WHEN any(calls_merged.ended_at) IS NULL THEN {pb_2:String}
            ELSE {pb_3:String}
        END DESC
        """,
        {
            "pb_0": '$."status_counts"."error"',
            "pb_1": "error",
            "pb_2": "running",
            "pb_3": "success",
            "pb_4": "descendant_error",
            "pb_5": "project",
        },
    )


def test_calls_query_with_predicate_filters_multiple_heavy_conditions() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_field("output")
    cq.add_condition(
        tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    {
                        "$eq": [
                            {"$getField": "inputs.param.val"},
                            {"$literal": "hello"},
                        ]
                    },  # <-- heavy condition on start-only field
                    {
                        "$eq": [
                            {"$getField": "output.result"},
                            {"$literal": "success"},
                        ]
                    },  # <-- heavy condition on end-only field
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
            PREWHERE calls_merged.project_id = {pb_7:String}
            WHERE ((calls_merged.inputs_dump LIKE {pb_5:String} OR calls_merged.inputs_dump IS NULL)
                    AND (calls_merged.output_dump LIKE {pb_6:String} OR calls_merged.output_dump IS NULL))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}), 'null'), '') = {pb_1:String}))
                AND
                ((coalesce(nullIf(JSON_VALUE(any(calls_merged.output_dump), {pb_2:String}), 'null'), '') = {pb_3:String}))
                AND
                ((any(calls_merged.wb_user_id) = {pb_4:String}))
                AND ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump,
            any(calls_merged.output_dump) AS output_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_7:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        """,
        {
            "pb_0": '$."param"."val"',
            "pb_1": "hello",
            "pb_2": '$."result"',
            "pb_3": "success",
            "pb_4": "my_user_id",
            "pb_5": '%"hello"%',
            "pb_6": '%"success"%',
            "pb_7": "project",
        },
    )


def test_calls_query_with_or_between_start_and_end_fields() -> None:
    """Test that we create predicate filters when there's an OR between start and end fields."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_field("output")
    cq.add_condition(
        tsi_query.OrOperation.model_validate(
            {
                "$or": [
                    {
                        "$eq": [
                            {"$getField": "inputs.param.val"},
                            {"$literal": "hello"},
                        ]
                    },  # <-- heavy condition on start-only field
                    {
                        "$eq": [
                            {"$getField": "output.result"},
                            {"$literal": "success"},
                        ]
                    },  # <-- heavy condition on end-only field
                ]
            }
        )
    )
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump,
            any(calls_merged.output_dump) AS output_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_6:String}
        WHERE (((calls_merged.inputs_dump LIKE {pb_4:String} OR calls_merged.inputs_dump IS NULL)
                OR (calls_merged.output_dump LIKE {pb_5:String} OR calls_merged.output_dump IS NULL)))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING ((
            ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}), 'null'), '') = {pb_1:String})
            OR
            (coalesce(nullIf(JSON_VALUE(any(calls_merged.output_dump), {pb_2:String}), 'null'), '') = {pb_3:String})))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        """,
        {
            "pb_0": '$."param"."val"',
            "pb_1": "hello",
            "pb_2": '$."result"',
            "pb_3": "success",
            "pb_4": '%"hello"%',
            "pb_5": '%"success"%',
            "pb_6": "project",
        },
    )


def test_calls_query_with_complex_heavy_filters() -> None:
    """Test complex combinations of heavy filter conditions on inputs and outputs."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_field("output")

    # Create a complex query with multiple conditions on inputs and outputs
    cq.add_condition(
        tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    # Multiple conditions on inputs
                    {
                        "$eq": [
                            {"$getField": "inputs.param.val"},
                            {"$literal": "hello"},
                        ]
                    },
                    {
                        "$gt": [
                            {"$getField": "inputs.param.count"},
                            {"$literal": 5},
                        ]
                    },
                    {
                        # Multiple conditions in nested OR
                        "$or": [
                            {
                                "$eq": [
                                    {"$getField": "output.result.status"},
                                    {"$literal": "success"},
                                ]
                            },
                            {
                                "$contains": {
                                    "input": {"$getField": "inputs.param.message"},
                                    "substr": {"$literal": "completed"},
                                    "case_insensitive": True,
                                }
                            },
                        ]
                    },
                    # Light condition
                    {"$eq": [{"$getField": "wb_user_id"}, {"$literal": "my_user_id"}]},
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
            PREWHERE calls_merged.project_id = {pb_12:String}
            WHERE (
                (calls_merged.inputs_dump LIKE {pb_9:String} OR calls_merged.inputs_dump IS NULL)
                AND ((calls_merged.output_dump LIKE {pb_10:String} OR calls_merged.output_dump IS NULL)
                    OR (lower(calls_merged.inputs_dump) LIKE {pb_11:String} OR calls_merged.inputs_dump IS NULL)))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}), 'null'), '') = {pb_1:String}))
                AND
                ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_2:String}), 'null'), '') > {pb_3:UInt64}))
                AND (((coalesce(nullIf(JSON_VALUE(any(calls_merged.output_dump), {pb_4:String}), 'null'), '') = {pb_5:String})
                  OR positionCaseInsensitive(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_6:String}), 'null'), ''), {pb_7:String}) > 0))
                AND
                ((any(calls_merged.wb_user_id) = {pb_8:String}))
                AND ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump,
            any(calls_merged.output_dump) AS output_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_12:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        """,
        {
            "pb_0": '$."param"."val"',
            "pb_1": "hello",
            "pb_2": '$."param"."count"',
            "pb_3": 5,
            "pb_4": '$."result"."status"',
            "pb_5": "success",
            "pb_6": '$."param"."message"',
            "pb_7": "completed",
            "pb_8": "my_user_id",
            "pb_9": '%"hello"%',
            "pb_10": '%"success"%',
            "pb_11": '%"%completed%"%',
            "pb_12": "project",
        },
    )


def test_calls_query_with_like_optimization() -> None:
    """Test that simple JSON field equality checks use LIKE optimization."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "inputs.param"},
                    {"$literal": "hello"},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_3:String}
        WHERE ((calls_merged.inputs_dump LIKE {pb_2:String} OR calls_merged.inputs_dump IS NULL))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}), 'null'), '') = {pb_1:String}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {
            "pb_3": "project",
            "pb_2": '%"hello"%',
            "pb_1": "hello",
            "pb_0": '$."param"',
        },
    )


def test_calls_query_with_like_optimization_contains() -> None:
    """Test that contains operations on JSON fields use LIKE optimization."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.ContainsOperation.model_validate(
            {
                "$contains": {
                    "input": {"$getField": "inputs.param"},
                    "substr": {"$literal": "hello"},
                    "case_insensitive": True,
                }
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_3:String}
        WHERE ((lower(calls_merged.inputs_dump) LIKE {pb_2:String} OR calls_merged.inputs_dump IS NULL))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            (positionCaseInsensitive(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}), 'null'), ''), {pb_1:String}) > 0)
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {
            "pb_0": '$."param"',
            "pb_3": "project",
            "pb_2": '%"%hello%"%',
            "pb_1": "hello",
        },
    )


def test_query_with_json_value_in_condition() -> None:
    """Test that in operations on JSON fields use JSON_VALUE with IN."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.InOperation.model_validate(
            {
                "$in": [
                    {"$getField": "inputs.param"},
                    [{"$literal": "hello"}, {"$literal": "world"}],
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_5:String}
        WHERE (((calls_merged.inputs_dump LIKE {pb_3:String} OR calls_merged.inputs_dump LIKE {pb_4:String})
                OR calls_merged.inputs_dump IS NULL))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}), 'null'), '') IN ({pb_1:String},{pb_2:String})))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {
            "pb_0": '$."param"',
            "pb_1": "hello",
            "pb_2": "world",
            "pb_5": "project",
            "pb_3": '%"hello"%',
            "pb_4": '%"world"%',
        },
    )


def test_calls_query_with_like_optimization_calls_complete() -> None:
    """Test that LIKE optimization on calls_complete does NOT include null checks.

    For calls_complete, every row is a complete call, so there are no unmerged
    call parts with NULL fields. The LIKE condition should be tighter without
    the OR IS NULL clause.
    """
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "inputs.param"},
                    {"$literal": "hello"},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT
            calls_complete.id AS id
        FROM calls_complete
        PREWHERE calls_complete.project_id = {pb_3:String}
        WHERE (calls_complete.inputs_dump LIKE {pb_2:String})
        AND
            (((coalesce(nullIf(JSON_VALUE(calls_complete.inputs_dump, {pb_0:String}), 'null'), '') = {pb_1:String}))
                AND ((calls_complete.deleted_at IS NULL))
                    AND ((NOT ((calls_complete.started_at IS NULL)))))
        """,
        {
            "pb_3": "project",
            "pb_2": '%"hello"%',
            "pb_1": "hello",
            "pb_0": '$."param"',
        },
    )


def test_calls_query_with_like_optimization_contains_calls_complete() -> None:
    """Test that contains LIKE optimization on calls_complete does NOT include null checks."""
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.ContainsOperation.model_validate(
            {
                "$contains": {
                    "input": {"$getField": "inputs.param"},
                    "substr": {"$literal": "hello"},
                    "case_insensitive": True,
                }
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT
            calls_complete.id AS id
        FROM calls_complete
        PREWHERE calls_complete.project_id = {pb_3:String}
        WHERE (lower(calls_complete.inputs_dump) LIKE {pb_2:String})
        AND
            ((positionCaseInsensitive(coalesce(nullIf(JSON_VALUE(calls_complete.inputs_dump, {pb_0:String}), 'null'), ''), {pb_1:String}) > 0)
                AND ((calls_complete.deleted_at IS NULL))
                    AND ((NOT ((calls_complete.started_at IS NULL)))))
        """,
        {
            "pb_0": '$."param"',
            "pb_3": "project",
            "pb_2": '%"%hello%"%',
            "pb_1": "hello",
        },
    )


def test_calls_query_with_like_optimization_in_calls_complete() -> None:
    """Test that IN LIKE optimization on calls_complete does NOT include null checks."""
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.InOperation.model_validate(
            {
                "$in": [
                    {"$getField": "inputs.param"},
                    [{"$literal": "hello"}, {"$literal": "world"}],
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT
            calls_complete.id AS id
        FROM calls_complete
        PREWHERE calls_complete.project_id = {pb_5:String}
        WHERE ((calls_complete.inputs_dump LIKE {pb_3:String} OR calls_complete.inputs_dump LIKE {pb_4:String}))
        AND
            (((coalesce(nullIf(JSON_VALUE(calls_complete.inputs_dump, {pb_0:String}), 'null'), '') IN ({pb_1:String},{pb_2:String})))
                AND ((calls_complete.deleted_at IS NULL))
                    AND ((NOT ((calls_complete.started_at IS NULL)))))
        """,
        {
            "pb_0": '$."param"',
            "pb_1": "hello",
            "pb_2": "world",
            "pb_5": "project",
            "pb_3": '%"hello"%',
            "pb_4": '%"world"%',
        },
    )


def test_calls_query_with_combined_like_optimizations_and_op_filter() -> None:
    """Test combining multiple LIKE optimizations with different operators and fields."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("attributes")
    cq.add_field("inputs")

    # Add a hardcoded filter for op_names
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
                op_names=["llm/openai", "llm/anthropic"],
            )
        )
    )

    # Add a complex condition with multiple operators on different fields
    cq.add_condition(
        tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    # Equality on attributes
                    {
                        "$eq": [
                            {"$getField": "attributes.model"},
                            {"$literal": "gpt-4"},
                        ]
                    },
                    # Contains on inputs
                    {
                        "$contains": {
                            "input": {"$getField": "inputs.prompt"},
                            "substr": {"$literal": "weather"},
                            "case_insensitive": True,
                        }
                    },
                    # In operation on attributes
                    {
                        "$in": [
                            {"$getField": "attributes.temperature"},
                            [{"$literal": "0.7"}, {"$literal": "0.8"}],
                        ]
                    },
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
            PREWHERE calls_merged.project_id = {pb_12:String}
            WHERE ((calls_merged.op_name IN {pb_7:Array(String)})
                    OR (calls_merged.op_name IS NULL))
                AND ((calls_merged.attributes_dump LIKE {pb_8:String} OR calls_merged.attributes_dump IS NULL)
                    AND (lower(calls_merged.inputs_dump) LIKE {pb_9:String} OR calls_merged.inputs_dump IS NULL)
                    AND ((calls_merged.attributes_dump LIKE {pb_10:String} OR calls_merged.attributes_dump LIKE {pb_11:String})
                        OR calls_merged.attributes_dump IS NULL))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_0:String}), 'null'), '') = {pb_1:String}))
                AND
                (positionCaseInsensitive(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_2:String}), 'null'), ''), {pb_3:String}) > 0)
                AND
                ((coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_4:String}), 'null'), '') IN ({pb_5:String},{pb_6:String})))
                AND ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.attributes_dump) AS attributes_dump,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_12:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        """,
        {
            "pb_0": '$."model"',
            "pb_1": "gpt-4",
            "pb_2": '$."prompt"',
            "pb_3": "weather",
            "pb_4": '$."temperature"',
            "pb_5": "0.7",
            "pb_6": "0.8",
            "pb_7": ["llm/openai", "llm/anthropic"],
            "pb_8": '%"gpt-4"%',
            "pb_9": '%"%weather%"%',
            "pb_10": '%"0.7"%',
            "pb_11": '%"0.8"%',
            "pb_12": "project",
        },
    )


def test_calls_query_with_unoptimizable_or_condition() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_condition(
        tsi_query.OrOperation.model_validate(
            {
                "$or": [
                    {"$eq": [{"$getField": "inputs.param.val"}, {"$literal": "hello"}]},
                    {"$gt": [{"$getField": "inputs.param.number"}, {"$literal": 10}]},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_5:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((
            (coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}), 'null'), '') = {pb_1:String})
            OR (coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_2:String}), 'null'), '') > {pb_3:UInt64})))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {
            "pb_0": '$."param"."val"',
            "pb_1": "hello",
            "pb_2": '$."param"."number"',
            "pb_3": 10,
            "pb_4": '%"hello"%',
            "pb_5": "project",
        },
    )


def test_calls_query_filter_by_empty_string() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {"$eq": [{"$getField": "inputs.param.val"}, {"$literal": ""}]}
        )
    )
    # Empty string is not a valid value for LIKE optimization, this test ensures we do
    # not try to optimize
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_2:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}), 'null'), '') = {pb_1:String}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {
            "pb_0": '$."param"."val"',
            "pb_1": "",
            "pb_2": "project",
        },
    )


def test_query_with_summary_weave_latency_ms_sort() -> None:
    """Test sorting by summary.weave.latency_ms field."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_field("ended_at")
    cq.add_order("summary.weave.latency_ms", "desc")

    # Assert that the query orders by the computed latency field
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id,
            any(calls_merged.started_at) AS started_at,
            any(calls_merged.ended_at) AS ended_at
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_0:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((
                any(calls_merged.deleted_at) IS NULL
            ))
            AND
            ((
               NOT ((
                  any(calls_merged.started_at) IS NULL
               ))
            ))
        )
        ORDER BY CASE
            WHEN any(calls_merged.ended_at) IS NULL THEN NULL
            ELSE (toUnixTimestamp64Milli(any(calls_merged.ended_at)) - toUnixTimestamp64Milli(any(calls_merged.started_at)))
        END DESC
        """,
        {"pb_0": "project"},
    )


def test_query_with_summary_weave_latency_ms_filter() -> None:
    """Test filtering by summary.weave.latency_ms field."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_field("ended_at")

    # Add a condition to filter for calls with latency greater than 1000ms (1s)
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {"$gt": [{"$getField": "summary.weave.latency_ms"}, {"$literal": 1000}]}
        )
    )

    # Assert that the query includes a filter on the latency field
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id,
            any(calls_merged.started_at) AS started_at,
            any(calls_merged.ended_at) AS ended_at
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_1:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((CASE
              WHEN any(calls_merged.ended_at) IS NULL THEN NULL
              ELSE (toUnixTimestamp64Milli(any(calls_merged.ended_at)) - toUnixTimestamp64Milli(any(calls_merged.started_at)))
          END > {pb_0:UInt64}))
        AND ((any(calls_merged.deleted_at) IS NULL))
        AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        """,
        {"pb_0": 1000, "pb_1": "project"},
    )


def test_query_with_summary_weave_trace_name_sort() -> None:
    """Test sorting by summary.weave.trace_name field."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("op_name")
    cq.add_field("display_name")
    cq.add_order("summary.weave.trace_name", "asc")

    # Assert that the query orders by the computed trace_name field
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id,
            any(calls_merged.op_name) AS op_name,
            argMaxMerge(calls_merged.display_name) AS display_name
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_0:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((
                any(calls_merged.deleted_at) IS NULL
            ))
            AND
            ((
               NOT ((
                  any(calls_merged.started_at) IS NULL
               ))
            ))
        )
        ORDER BY CASE
            WHEN argMaxMerge(calls_merged.display_name) IS NOT NULL AND argMaxMerge(calls_merged.display_name) != '' THEN argMaxMerge(calls_merged.display_name)
            WHEN any(calls_merged.op_name) IS NOT NULL AND any(calls_merged.op_name) LIKE 'weave-trace-internal:///%' THEN
                regexpExtract(toString(any(calls_merged.op_name)), '/([^/:]*):', 1)
            ELSE any(calls_merged.op_name)
        END ASC
        """,
        {"pb_0": "project"},
    )


def test_query_with_summary_weave_trace_name_filter() -> None:
    """Test filtering by summary.weave.trace_name field."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("op_name")
    cq.add_field("display_name")

    # Add a condition to filter for calls with a specific trace name
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "summary.weave.trace_name"},
                    {"$literal": "my_model"},
                ]
            }
        )
    )

    # Assert that the query includes a filter on the trace_name field
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id,
            any(calls_merged.op_name) AS op_name,
            argMaxMerge(calls_merged.display_name) AS display_name
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_1:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((CASE
                WHEN argMaxMerge(calls_merged.display_name) IS NOT NULL AND argMaxMerge(calls_merged.display_name) != '' THEN argMaxMerge(calls_merged.display_name)
                WHEN any(calls_merged.op_name) IS NOT NULL AND any(calls_merged.op_name) LIKE 'weave-trace-internal:///%' THEN
                    regexpExtract(toString(any(calls_merged.op_name)), '/([^/:]*):', 1)
                ELSE any(calls_merged.op_name)
            END = {pb_0:String}))
        AND ((any(calls_merged.deleted_at) IS NULL))
        AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        """,
        {"pb_0": "my_model", "pb_1": "project"},
    )


def test_build_calls_complete_update_end_query() -> None:
    """Ensure the update-end helper builds the expected query."""
    query = build_calls_complete_update_end_query(
        table_name="calls_complete",
        project_id_param="project_id",
        started_at_param="started_at",
        id_param="id",
        ended_at_param="ended_at",
        exception_param="exception",
        output_dump_param="output_dump",
        summary_dump_param="summary_dump",
        output_refs_param="output_refs",
        wb_run_step_end_param="wb_run_step_end",
    )

    expected = """
        UPDATE calls_complete
        SET
            ended_at = fromUnixTimestamp64Micro({ended_at:Int64}, 'UTC'),
            exception = {exception:Nullable(String)},
            output_dump = {output_dump:String},
            summary_dump = {summary_dump:String},
            output_refs = {output_refs:Array(String)},
            wb_run_step_end = {wb_run_step_end:Nullable(UInt64)},
            updated_at = now64(3)
        WHERE project_id = {project_id:String}
            AND started_at = fromUnixTimestamp64Micro({started_at:Int64}, 'UTC')
            AND id = {id:String}
    """

    exp_formatted = sqlparse.format(expected, reindent=True)
    found_formatted = sqlparse.format(query, reindent=True)

    assert exp_formatted == found_formatted, (
        f"\nExpected:\n{exp_formatted}\n\nGot:\n{found_formatted}"
    )


def test_storage_size_fields():
    """Test querying with storage size fields."""
    cq = CallsQuery(project_id="test/project", include_storage_size=True)
    cq.add_field("id")
    cq.add_field("storage_size_bytes")

    assert_sql(
        cq,
        """
        SELECT calls_merged.id AS id,
           any(storage_size_tbl.storage_size_bytes) AS storage_size_bytes
        FROM calls_merged
        LEFT JOIN
        (SELECT id,
                sum(COALESCE(attributes_size_bytes, 0) + COALESCE(inputs_size_bytes, 0) + COALESCE(output_size_bytes, 0) + COALESCE(summary_size_bytes, 0)) AS storage_size_bytes
        FROM calls_merged_stats
        WHERE project_id = {pb_0:String}
        GROUP BY id) AS storage_size_tbl ON calls_merged.id = storage_size_tbl.id
        PREWHERE calls_merged.project_id = {pb_0:String}
        GROUP BY (calls_merged.project_id,
                calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        """,
        {"pb_0": "test/project"},
    )


@pytest.mark.parametrize("with_filter", [False, True])
def test_total_storage_size(with_filter: bool):
    """Test querying with total storage size.

    Args:
        with_filter: If True, test the optimized case where trace_id filtering is added
                     to the total_storage_size JOIN via the filtered_calls CTE.
    """
    cq = CallsQuery(project_id="test/project", include_total_storage_size=True)
    cq.add_field("id")
    cq.add_field("total_storage_size_bytes")

    if with_filter:
        # Add a heavy field (inputs) to trigger the filtered_calls CTE optimization
        cq.add_field("inputs_dump")
        # Add a filter to trigger the optimization path
        cq.set_hardcoded_filter(
            HardCodedFilter(filter=tsi.CallsFilter(op_names=["a", "b"]))
        )

        # Expected SQL with the filtered_calls CTE and trace_id filter in the JOIN
        assert_sql(
            cq,
            """
            WITH filtered_calls AS (
                SELECT
                    calls_merged.id AS id
                FROM calls_merged
                PREWHERE calls_merged.project_id = {pb_1:String}
                WHERE ((calls_merged.op_name IN {pb_0:Array(String)})
                    OR (calls_merged.op_name IS NULL))
                GROUP BY (calls_merged.project_id, calls_merged.id)
                HAVING (((any(calls_merged.deleted_at) IS NULL))
                    AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
            )
            SELECT
                calls_merged.id AS id,
                CASE
                    WHEN any(calls_merged.parent_id) IS NULL
                    THEN any(rolled_up_cms.total_storage_size_bytes)
                    ELSE NULL
                END AS total_storage_size_bytes,
                any(calls_merged.inputs_dump) AS inputs_dump
            FROM calls_merged
            LEFT JOIN (SELECT
                trace_id,
                sum(COALESCE(attributes_size_bytes,0) + COALESCE(inputs_size_bytes,0) + COALESCE(output_size_bytes,0) + COALESCE(summary_size_bytes,0)) AS total_storage_size_bytes
            FROM calls_merged_stats
            WHERE project_id = {pb_1:String}
            AND trace_id IN (
                SELECT trace_id
                FROM calls_merged
                WHERE project_id = {pb_1:String}
                AND id IN filtered_calls
            )
            GROUP BY trace_id) AS rolled_up_cms
            ON calls_merged.trace_id = rolled_up_cms.trace_id
            PREWHERE calls_merged.project_id = {pb_1:String}
            WHERE (calls_merged.id IN filtered_calls)
            GROUP BY (calls_merged.project_id, calls_merged.id)
            """,
            {"pb_0": ["a", "b"], "pb_1": "test/project"},
        )
    else:
        # Expected SQL without filters (baseline case)
        assert_sql(
            cq,
            """
            SELECT
                calls_merged.id AS id,
                CASE
                    WHEN any(calls_merged.parent_id) IS NULL
                    THEN any(rolled_up_cms.total_storage_size_bytes)
                    ELSE NULL
                END AS total_storage_size_bytes
            FROM calls_merged
            LEFT JOIN (SELECT
                trace_id,
                sum(COALESCE(attributes_size_bytes,0) + COALESCE(inputs_size_bytes,0) + COALESCE(output_size_bytes,0) + COALESCE(summary_size_bytes,0)) AS total_storage_size_bytes
            FROM calls_merged_stats
            WHERE project_id = {pb_0:String}
            GROUP BY trace_id) AS rolled_up_cms
            ON calls_merged.trace_id = rolled_up_cms.trace_id
            PREWHERE calls_merged.project_id = {pb_0:String}
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
            """,
            {"pb_0": "test/project"},
        )


def test_aggregated_data_size_field():
    """Test the AggregatedDataSizeField class."""
    field = AggregatedDataSizeField(
        field="total_storage_size_bytes", join_table_name="rolled_up_cms"
    )
    pb = ParamBuilder()

    # Test SQL generation
    sql = field.as_select_sql(pb, "calls_merged")
    assert "CASE" in sql
    assert "parent_id" in sql
    assert "rolled_up_cms.total_storage_size_bytes" in sql


def test_datetime_optimization_simple() -> None:
    """Test basic datetime optimization with a single timestamp condition."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {"$getField": "started_at"},
                    {"$literal": 1709251200},  # 2024-03-01 00:00:00 UTC
                ]
            }
        )
    )

    # The optimization should add a condition on the ID field based on the UUIDv7 timestamp
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_2:String}
        WHERE (calls_merged.sortable_datetime > {pb_1:String})
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((any(calls_merged.started_at) > {pb_0:UInt64}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {
            "pb_0": 1709251200,
            "pb_2": "project",
            "pb_1": "2024-02-29 23:55:00.000000",
        },
    )


def test_datetime_optimization_lt_simple() -> None:
    """Test basic datetime optimization with a single LT timestamp condition."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.LtOperation.model_validate(
            {
                "$lt": [
                    {"$getField": "started_at"},
                    {"$literal": 1709251200},  # 2024-03-01 00:00:00 UTC
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_2:String}
        WHERE (calls_merged.sortable_datetime < {pb_1:String})
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((any(calls_merged.started_at) < {pb_0:UInt64}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {
            "pb_0": 1709251200,
            "pb_2": "project",
            "pb_1": "2024-03-01 00:05:00.000000",
        },
    )


def test_datetime_optimization_not_operation() -> None:
    """Test datetime optimization with a NOT operation."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.NotOperation.model_validate(
            {
                "$not": [
                    {
                        "$gte": [
                            {"$getField": "started_at"},
                            {"$literal": 1709251200},  # 2024-03-01 00:00:00 UTC
                        ]
                    }
                ]
            }
        )
    )

    # The optimization should add a condition on the ID field with reversed comparison
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_2:String}
        WHERE (NOT (calls_merged.sortable_datetime >= {pb_1:String}))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING ((
            (NOT ((any(calls_merged.started_at) >= {pb_0:UInt64}))))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {
            "pb_0": 1709251200,
            "pb_2": "project",
            "pb_1": "2024-03-01 00:05:00.000000",
        },
    )


def test_datetime_optimization_multiple_conditions() -> None:
    """Test datetime optimization with multiple timestamp conditions."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    {
                        "$and": [
                            {
                                "$gt": [
                                    {"$getField": "started_at"},
                                    {"$literal": 1709251200},  # 2024-03-01 00:00:00 UTC
                                ]
                            },
                            {
                                "$not": [
                                    {
                                        "$gt": [
                                            {"$getField": "started_at"},
                                            {
                                                "$literal": 1709337600
                                            },  # 2024-03-02 00:00:00 UTC
                                        ]
                                    }
                                ]
                            },
                        ]
                    },
                    {
                        "$or": [
                            {
                                "$gt": [
                                    {"$getField": "ended_at"},
                                    {"$literal": 1709251200},
                                ]
                            },
                            {
                                "$and": [
                                    {
                                        "$gte": [
                                            {"$getField": "ended_at"},
                                            {"$literal": 1709251200},
                                        ]
                                    },
                                    {
                                        "$gt": [
                                            {"$getField": "ended_at"},
                                            {"$literal": 1709337600},
                                        ]
                                    },
                                ]
                            },
                        ]
                    },
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_4:String}
        WHERE (calls_merged.sortable_datetime > {pb_2:String}
            AND NOT (calls_merged.sortable_datetime > {pb_3:String}))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((any(calls_merged.started_at) > {pb_0:UInt64}))
            AND ((NOT ((any(calls_merged.started_at) > {pb_1:UInt64}))))
            AND (((any(calls_merged.ended_at) > {pb_0:UInt64})
                OR ((any(calls_merged.ended_at) >= {pb_0:UInt64})
                    AND (any(calls_merged.ended_at) > {pb_1:UInt64}))))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {
            "pb_0": 1709251200,
            "pb_1": 1709337600,
            "pb_4": "project",
            "pb_2": "2024-02-29 23:55:00.000000",
            "pb_3": "2024-03-02 00:05:00.000000",
        },
    )


def test_datetime_optimization_invalid_field() -> None:
    """Test that datetime optimization is not applied for non-timestamp fields."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {"$getField": "wb_user_id"},
                    {"$literal": 1709251200},
                ]
            }
        )
    )
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {"$getField": "started_at"},
                    {"$literal": "2025-03-01 00:00:00 UTC"},
                ]
            }
        )
    )

    # The optimization should not be applied since wb_user_id is not a timestamp field
    # and '2025-03-01 00:00:00 UTC' isn't a timestamp
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_2:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((any(calls_merged.wb_user_id) > {pb_0:UInt64}))
            AND ((any(calls_merged.started_at) > {pb_1:String}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": 1709251200, "pb_1": "2025-03-01 00:00:00 UTC", "pb_2": "project"},
    )


def test_query_with_feedback_filter_and_datetime_and_string_filter() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    {
                        "$gt": [
                            {
                                "$getField": "feedback.[wandb.runnable.my_op].payload.output.expected"
                            },
                            {
                                "$getField": "feedback.[wandb.runnable.my_op].payload.output.found"
                            },
                        ]
                    },
                    {
                        "$gt": [
                            {"$getField": "started_at"},
                            {"$literal": 1709251200},
                        ]
                    },
                    {
                        "$eq": [
                            {"$getField": "inputs.message"},
                            {"$literal": "hello"},
                        ]
                    },
                ]
            }
        )
    )
    assert_sql(
        cq,
        """
        WITH filtered_calls AS
            (SELECT calls_merged.id AS id
            FROM calls_merged
                            LEFT JOIN (SELECT * FROM feedback WHERE feedback.project_id = {pb_8:String} ) AS feedback ON (feedback.weave_ref = concat('weave-trace-internal:///', {pb_8:String}, '/call/', calls_merged.id))
            PREWHERE calls_merged.project_id = {pb_8:String}
            WHERE (calls_merged.sortable_datetime > {pb_7:String})
                AND ((calls_merged.inputs_dump LIKE {pb_6:String}
                    OR calls_merged.inputs_dump IS NULL))
            GROUP BY (calls_merged.project_id,
                        calls_merged.id)
            HAVING (((coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_1:String}), 'null'), '') > coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_2:String}), 'null'), '')))
                AND ((any(calls_merged.started_at) > {pb_3:UInt64}))
                AND ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_4:String}), 'null'), '') = {pb_5:String}))
                AND ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))))
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_8:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id,
                calls_merged.id)
        """,
        {
            "pb_0": "wandb.runnable.my_op",
            "pb_1": '$."output"."expected"',
            "pb_2": '$."output"."found"',
            "pb_3": 1709251200,
            "pb_4": '$."message"',
            "pb_5": "hello",
            "pb_6": '%"hello"%',
            "pb_7": "2024-02-29 23:55:00.000000",
            "pb_8": "project",
        },
    )


def test_trace_id_filter_in():
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.hardcoded_filter = HardCodedFilter(
        filter={"trace_ids": ["111111111111", "222222222222"]}
    )
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_1:String}
        WHERE (calls_merged.trace_id IN {pb_0:Array(String)}
                OR calls_merged.trace_id IS NULL)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        """,
        {"pb_0": ["111111111111", "222222222222"], "pb_1": "project"},
    )


def test_trace_id_filter_eq():
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.hardcoded_filter = HardCodedFilter(
        filter={
            "trace_ids": ["111111111111"],
            "op_names": ["weave-trace-internal:///%"],
        }
    )
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_2:String}
        WHERE ((calls_merged.op_name IN {pb_0:Array(String)})
                OR (calls_merged.op_name IS NULL))
            AND (calls_merged.trace_id = {pb_1:String}
                OR calls_merged.trace_id IS NULL)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        """,
        {
            "pb_1": "111111111111",
            "pb_0": ["weave-trace-internal:///%"],
            "pb_2": "project",
        },
    )


def test_wb_run_id_filter_eq():
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.hardcoded_filter = HardCodedFilter(filter={"wb_run_ids": ["wb_run_123"]})
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_2:String}
        WHERE (calls_merged.wb_run_id IN {pb_1:Array(String)}
                OR calls_merged.wb_run_id IS NULL)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            AND (any(calls_merged.wb_run_id) IN {pb_0:Array(String)}))
        """,
        {"pb_0": ["wb_run_123"], "pb_1": ["wb_run_123"], "pb_2": "project"},
    )


def test_trace_roots_only_filter_with_condition():
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.hardcoded_filter = HardCodedFilter(filter={"trace_roots_only": True})
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "wb_user_id"},
                    {"$literal": 1},
                ]
            }
        )
    )
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_1:String}
        WHERE (calls_merged.parent_id IS NULL)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((any(calls_merged.wb_user_id) = {pb_0:UInt64}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        """,
        {"pb_0": 1, "pb_1": "project"},
    )


def test_parent_id_filter():
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.hardcoded_filter = HardCodedFilter(
        filter={"parent_ids": ["111111111111", "222222222222"]}
    )
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_2:String}
        WHERE (calls_merged.parent_id IN {pb_1:Array(String)}
                OR calls_merged.parent_id IS NULL)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            AND (any(calls_merged.parent_id) IN {pb_0:Array(String)}))
        """,
        {
            "pb_0": ["111111111111", "222222222222"],
            "pb_1": ["111111111111", "222222222222"],
            "pb_2": "project",
        },
    )


def test_input_output_refs_filter():
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.hardcoded_filter = HardCodedFilter(
        filter={
            "input_refs": ["weave-trace-internal:///222222222222%"],
            "output_refs": ["weave-trace-internal:///111111111111%"],
        }
    )
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_4:String}
        WHERE (((hasAny(calls_merged.input_refs, {pb_2:Array(String)})
                OR length(calls_merged.input_refs) = 0)
            AND (hasAny(calls_merged.output_refs, {pb_3:Array(String)})
                OR length(calls_merged.output_refs) = 0)))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            AND (((hasAny(array_concat_agg(calls_merged.input_refs), {pb_0:Array(String)}))
                AND (hasAny(array_concat_agg(calls_merged.output_refs), {pb_1:Array(String)})))))
        """,
        {
            "pb_4": "project",
            "pb_0": ["weave-trace-internal:///222222222222%"],
            "pb_1": ["weave-trace-internal:///111111111111%"],
            "pb_2": ["weave-trace-internal:///222222222222%"],
            "pb_3": ["weave-trace-internal:///111111111111%"],
        },
    )


def test_all_optimization_filters():
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.hardcoded_filter = HardCodedFilter(
        filter={
            "input_refs": ["weave-trace-internal:///222222222222%"],
            "output_refs": ["weave-trace-internal:///111111111111%"],
            "trace_ids": ["111111111111", "222222222222"],
            "op_names": [
                "weave-trace-internal:///222222222222",
                "weave-trace-internal:///111111111111",
            ],
            "parent_ids": ["111111111111", "222222222222"],
            "thread_ids": ["thread_333", "thread_444"],
            "turn_ids": ["turn_555", "turn_666"],
        }
    )
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_12:String}
        WHERE (calls_merged.parent_id IN {pb_11:Array(String)}
                OR calls_merged.parent_id IS NULL)
            AND ((calls_merged.op_name IN {pb_5:Array(String)})
                OR (calls_merged.op_name IS NULL))
            AND (calls_merged.trace_id IN {pb_6:Array(String)}
                OR calls_merged.trace_id IS NULL)
            AND (calls_merged.thread_id IN {pb_7:Array(String)}
                OR calls_merged.thread_id IS NULL)
            AND (calls_merged.turn_id IN {pb_8:Array(String)}
                OR calls_merged.turn_id IS NULL)
            AND (((hasAny(calls_merged.input_refs, {pb_9:Array(String)})
                OR length(calls_merged.input_refs) = 0)
                AND (hasAny(calls_merged.output_refs, {pb_10:Array(String)})
                    OR length(calls_merged.output_refs) = 0)))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            AND (((hasAny(array_concat_agg(calls_merged.input_refs), {pb_0:Array(String)}))
                AND (hasAny(array_concat_agg(calls_merged.output_refs), {pb_1:Array(String)}))
            AND (any(calls_merged.parent_id) IN {pb_2:Array(String)})
              AND (any(calls_merged.thread_id) IN {pb_3:Array(String)})
              AND (any(calls_merged.turn_id) IN {pb_4:Array(String)}))))
        """,
        {
            "pb_0": ["weave-trace-internal:///222222222222%"],
            "pb_1": ["weave-trace-internal:///111111111111%"],
            "pb_2": ["111111111111", "222222222222"],
            "pb_3": ["thread_333", "thread_444"],
            "pb_4": ["turn_555", "turn_666"],
            "pb_5": [
                "weave-trace-internal:///222222222222",
                "weave-trace-internal:///111111111111",
            ],
            "pb_6": ["111111111111", "222222222222"],
            "pb_7": ["thread_333", "thread_444"],
            "pb_8": ["turn_555", "turn_666"],
            "pb_9": ["weave-trace-internal:///222222222222%"],
            "pb_10": ["weave-trace-internal:///111111111111%"],
            "pb_11": ["111111111111", "222222222222"],
            "pb_12": "project",
        },
    )


def test_filter_length_validation():
    """Test that filter length validation works."""
    pb = ParamBuilder()
    cq = CallsQuery(project_id="test/project")
    cq.hardcoded_filter = HardCodedFilter(
        filter={"op_names": ["weave-trace-internal:///%"] * 1001}
    )
    with pytest.raises(ValueError):
        cq.as_sql(pb)

    cq = CallsQuery(project_id="test/project")
    cq.hardcoded_filter = HardCodedFilter(
        filter={"input_refs": ["weave-trace-internal:///%"] * 1001}
    )
    with pytest.raises(ValueError):
        cq.as_sql(pb)

    cq = CallsQuery(project_id="test/project")
    cq.hardcoded_filter = HardCodedFilter(
        filter={"output_refs": ["weave-trace-internal:///%"] * 1001}
    )
    with pytest.raises(ValueError):
        cq.as_sql(pb)

    cq = CallsQuery(project_id="test/project")
    cq.hardcoded_filter = HardCodedFilter(
        filter={"parent_ids": ["weave-trace-internal:///%"] * 1001}
    )
    with pytest.raises(ValueError):
        cq.as_sql(pb)

    cq = CallsQuery(project_id="test/project")
    cq.hardcoded_filter = HardCodedFilter(
        filter={"trace_ids": ["weave-trace-internal:///%"] * 1001}
    )
    with pytest.raises(ValueError):
        cq.as_sql(pb)

    cq = CallsQuery(project_id="test/project")
    cq.hardcoded_filter = HardCodedFilter(
        filter={"call_ids": ["weave-trace-internal:///%"] * 1001}
    )
    with pytest.raises(ValueError):
        cq.as_sql(pb)
    cq = CallsQuery(project_id="test/project")
    cq.hardcoded_filter = HardCodedFilter(filter={"thread_ids": ["thread_123"] * 1001})
    with pytest.raises(ValueError):
        cq.as_sql(pb)

    cq = CallsQuery(project_id="test/project")
    cq.hardcoded_filter = HardCodedFilter(filter={"turn_ids": ["turn_123"] * 1001})
    with pytest.raises(ValueError):
        cq.as_sql(pb)

    cq = CallsQuery(project_id="test/project")
    cq.hardcoded_filter = HardCodedFilter(filter={"wb_run_ids": ["wb_run_123"] * 1001})
    with pytest.raises(ValueError):
        cq.as_sql(pb)

    # Test with too many conditions
    cq = CallsQuery(project_id="test/project")
    complex_conditions = {
        "$and": [
            {"$eq": [{"$getField": f"inputs.field{i}"}, {"$literal": i}]}
            for i in range(20)  # Exceeds MAX_CTES_PER_QUERY
        ]
    }
    cq.add_field("id")
    cq.add_condition(complex_conditions)
    cq.set_expand_columns(["inputs"])
    with pytest.raises(ValueError, match="Too many object reference conditions"):
        s = cq.as_sql(pb)


def test_disallowed_fields():
    cq = CallsQuery(project_id="test/project")
    # allowed order field
    cq.add_order("id", "ASC")
    with pytest.raises(ValueError):
        cq.add_order("storage_size_bytes", "ASC")
    with pytest.raises(ValueError):
        cq.add_order("total_storage_size_bytes", "DESC")
    # with bogus direction
    with pytest.raises(ValueError):
        cq.add_order("storage_size_bytes", "ASCDESC")
    # now try filtering with disallowed
    with pytest.raises(ValueError):
        cq.add_condition(
            tsi_query.GtOperation.model_validate(
                {
                    "$gt": [
                        {"$getField": "storage_size_bytes"},
                        {"$literal": 1},
                    ]
                }
            )
        )
        cq.as_sql(ParamBuilder())

    cq = CallsQuery(project_id="test/project")  # reset
    with pytest.raises(ValueError):
        cq.add_condition(
            tsi_query.GteOperation.model_validate(
                {
                    "$gte": [
                        {"$getField": "total_storage_size_bytes"},
                        {"$literal": 1},
                    ]
                }
            )
        )
        cq.as_sql(ParamBuilder())

    cq = CallsQuery(project_id="test/project")  # reset
    with pytest.raises(ValueError):
        cq.add_condition(
            tsi_query.LtOperation.model_validate(
                {
                    "$lt": [
                        {"$getField": "storage_size_bytes"},
                        {"$literal": 1},
                    ]
                }
            )
        )
        cq.as_sql(ParamBuilder())

    cq = CallsQuery(project_id="test/project")  # reset
    with pytest.raises(ValueError):
        cq.add_condition(
            tsi_query.LteOperation.model_validate(
                {
                    "$lte": [
                        {"$getField": "total_storage_size_bytes"},
                        {"$literal": 1},
                    ]
                }
            )
        )
        cq.as_sql(ParamBuilder())


def test_thread_id_filter_eq():
    """Test thread_id filter with single thread ID."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.hardcoded_filter = HardCodedFilter(filter={"thread_ids": ["thread_123"]})
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_2:String}
        WHERE (calls_merged.thread_id = {pb_1:String}
                OR calls_merged.thread_id IS NULL)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            AND (any(calls_merged.thread_id) IN {pb_0:Array(String)}))
        """,
        {"pb_0": ["thread_123"], "pb_1": "thread_123", "pb_2": "project"},
    )


def test_thread_id_filter_in():
    """Test thread_id filter with multiple thread IDs."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.hardcoded_filter = HardCodedFilter(
        filter={"thread_ids": ["thread_123", "thread_456"]}
    )
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_2:String}
        WHERE (calls_merged.thread_id IN {pb_1:Array(String)}
                OR calls_merged.thread_id IS NULL)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            AND (any(calls_merged.thread_id) IN {pb_0:Array(String)}))
        """,
        {
            "pb_0": ["thread_123", "thread_456"],
            "pb_1": ["thread_123", "thread_456"],
            "pb_2": "project",
        },
    )


def test_turn_id_filter_eq():
    """Test turn_id filter with single turn ID."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.hardcoded_filter = HardCodedFilter(filter={"turn_ids": ["turn_123"]})
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_2:String}
        WHERE (calls_merged.turn_id = {pb_1:String}
                OR calls_merged.turn_id IS NULL)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            AND (any(calls_merged.turn_id) IN {pb_0:Array(String)}))
        """,
        {"pb_0": ["turn_123"], "pb_1": "turn_123", "pb_2": "project"},
    )


def test_turn_id_filter_in():
    """Test turn_id filter with multiple turn IDs."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.hardcoded_filter = HardCodedFilter(filter={"turn_ids": ["turn_123", "turn_456"]})
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_2:String}
        WHERE (calls_merged.turn_id IN {pb_1:Array(String)}
                OR calls_merged.turn_id IS NULL)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            AND (any(calls_merged.turn_id) IN {pb_0:Array(String)}))
        """,
        {
            "pb_0": ["turn_123", "turn_456"],
            "pb_1": ["turn_123", "turn_456"],
            "pb_2": "project",
        },
    )


def test_thread_id_and_turn_id_filter_combined():
    """Test thread_id and turn_id filters together."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.hardcoded_filter = HardCodedFilter(
        filter={
            "thread_ids": ["thread_123", "thread_456"],
            "turn_ids": ["turn_789", "turn_abc"],
        }
    )
    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_4:String}
        WHERE (calls_merged.thread_id IN {pb_2:Array(String)}
                OR calls_merged.thread_id IS NULL)
            AND (calls_merged.turn_id IN {pb_3:Array(String)}
                OR calls_merged.turn_id IS NULL)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            AND (((any(calls_merged.thread_id) IN {pb_0:Array(String)})
              AND (any(calls_merged.turn_id) IN {pb_1:Array(String)}))))
        """,
        {
            "pb_0": ["thread_123", "thread_456"],
            "pb_1": ["turn_789", "turn_abc"],
            "pb_2": ["thread_123", "thread_456"],
            "pb_3": ["turn_789", "turn_abc"],
            "pb_4": "project",
        },
    )


def test_query_with_optimization_and_attributes_order() -> None:
    """Test ordering by attributes_dump when optimization is triggered (without costs).

    This test verifies that the fix works for any optimization scenario, not just costs.
    When a query has heavy fields (like inputs_dump) and is ordered by a field not
    explicitly selected, the optimization pattern creates CTEs and needs to ensure
    ordered fields are propagated.
    """
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs_dump")  # Heavy field - triggers optimization
    cq.add_order("started_at", "ASC")  # Order by field not explicitly selected
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
                op_names=["my_op"],  # Light filter - enables predicate pushdown
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
            PREWHERE calls_merged.project_id = {pb_1:String}
            WHERE ((calls_merged.op_name IN {pb_0:Array(String)})
                    OR (calls_merged.op_name IS NULL))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
            ORDER BY any(calls_merged.started_at) ASC
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_1:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        ORDER BY any(calls_merged.started_at) ASC
        """,
        {"pb_0": ["my_op"], "pb_1": "project"},
    )


def test_query_filter_with_escaped_dots_in_field_names() -> None:
    r"""Test filtering by fields with literal dots in their names.

    This tests the case where a JSON key actually contains dots in its name.
    For example: {"output": {"metrics.scorer.run": {"value": 42}}}

    Using escaped dots in the field path: "output.metrics\\.scorer\\.run.value"
    means we want to access: output["metrics.scorer.run"]["value"]
    NOT: output["metrics"]["scorer"]["run"]["value"]
    """
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    # Filter on a field with escaped dots
    # This means: output -> "metrics.scorer.run" (single key with dots) -> value
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "output.metrics\\.scorer\\.run.value"},
                    {"$literal": 42},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_3:String}
        WHERE ((calls_merged.output_dump LIKE {pb_2:String}
                OR calls_merged.output_dump IS NULL))
        GROUP BY (calls_merged.project_id,
                calls_merged.id)
        HAVING (((coalesce(nullIf(JSON_VALUE(any(calls_merged.output_dump), {pb_0:String}), 'null'), '') = {pb_1:UInt64}))
                AND ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        """,
        {
            "pb_0": '$."metrics.scorer.run"."value"',
            "pb_1": 42,
            "pb_2": "%42%",
            "pb_3": "project",
        },
    )


def test_calls_complete_with_light_filter_and_order() -> None:
    """Test calls_complete table with light filter conditions and ordering.

    This test demonstrates that for calls_complete, queries use direct column
    access without any() aggregation functions. Unlike calls_merged, calls_complete
    does not use GROUP BY or HAVING, and filter conditions go directly in the
    WHERE clause.
    """
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_field("op_name")
    cq.add_condition(
        tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    {
                        "$gt": [
                            {"$getField": "started_at"},
                            {"$literal": 1709251200},  # 2024-03-01 00:00:00 UTC
                        ]
                    },
                    {"$eq": [{"$getField": "wb_user_id"}, {"$literal": "user_123"}]},
                ]
            }
        )
    )
    cq.add_order("started_at", "desc")
    cq.set_limit(50)

    assert_sql(
        cq,
        """
        SELECT
            calls_complete.id AS id,
            calls_complete.started_at AS started_at,
            calls_complete.op_name AS op_name
        FROM calls_complete
        PREWHERE calls_complete.project_id = {pb_2:String}
        WHERE 1
          AND (
            ((calls_complete.started_at > {pb_0:UInt64}))
            AND ((calls_complete.wb_user_id = {pb_1:String}))
            AND ((calls_complete.deleted_at IS NULL))
            AND ((NOT ((calls_complete.started_at IS NULL))))
        )
        ORDER BY calls_complete.started_at DESC
        LIMIT 50
        """,
        {
            "pb_0": 1709251200,
            "pb_1": "user_123",
            "pb_2": "project",
        },
    )


def test_calls_complete_with_hardcoded_filter_and_json_condition_and_summary_order() -> (
    None
):
    """Test calls_complete table with hardcoded filter, JSON condition, and summary field ordering.

    This test demonstrates that for calls_complete, when there is a hardcoded filter
    (op_names, trace_ids) plus a JSON condition on summary, the optimizer creates a
    CTE to filter by the light conditions first, then joins back to get the full row.
    Additionally, it tests ordering by summary.weave.status which uses direct column
    access without any() aggregation functions (unlike calls_merged).
    """
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_field("exception")
    cq.add_field("ended_at")
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
                op_names=["my_op"],
                trace_ids=["trace_abc"],
            )
        )
    )
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {"$getField": "summary.latency"},
                    {"$literal": 1000},
                ]
            }
        )
    )
    cq.add_order("summary.weave.status", "asc")
    cq.set_limit(100)

    assert_sql(
        cq,
        """
        WITH filtered_calls AS (
            SELECT calls_complete.id AS id
            FROM calls_complete
            PREWHERE calls_complete.project_id = {pb_9:String}
            WHERE ((calls_complete.op_name IN {pb_2:Array(String)})
                    OR (calls_complete.op_name IS NULL))
                AND (calls_complete.trace_id = {pb_3:String}
                    OR calls_complete.trace_id IS NULL)
            AND (
                ((coalesce(nullIf(JSON_VALUE(calls_complete.summary_dump, {pb_0:String}), 'null'), '') > {pb_1:UInt64}))
                AND ((calls_complete.deleted_at IS NULL))
                AND ((NOT ((calls_complete.started_at IS NULL))))
            )
            ORDER BY CASE
                WHEN calls_complete.exception IS NOT NULL THEN {pb_5:String}
                WHEN IFNULL(
                    toInt64OrNull(
                        coalesce(nullIf(JSON_VALUE(calls_complete.summary_dump, {pb_4:String}), 'null'), '')
                    ),
                    0
                ) > 0 THEN {pb_8:String}
                WHEN calls_complete.ended_at IS NULL THEN {pb_6:String}
                ELSE {pb_7:String}
                END ASC
            LIMIT 100
        )
        SELECT
            calls_complete.id AS id,
            calls_complete.started_at AS started_at,
            calls_complete.exception AS exception,
            calls_complete.ended_at AS ended_at
        FROM calls_complete
        PREWHERE calls_complete.project_id = {pb_9:String}
        WHERE (calls_complete.id IN filtered_calls)
        ORDER BY CASE
            WHEN calls_complete.exception IS NOT NULL THEN {pb_5:String}
            WHEN IFNULL(
                toInt64OrNull(
                    coalesce(nullIf(JSON_VALUE(calls_complete.summary_dump, {pb_4:String}), 'null'), '')
                ),
                0
            ) > 0 THEN {pb_8:String}
            WHEN calls_complete.ended_at IS NULL THEN {pb_6:String}
            ELSE {pb_7:String}
            END ASC
        """,
        {
            "pb_0": '$."latency"',
            "pb_1": 1000,
            "pb_2": ["my_op"],
            "pb_3": "trace_abc",
            "pb_4": '$."status_counts"."error"',
            "pb_5": "error",
            "pb_6": "running",
            "pb_7": "success",
            "pb_8": "descendant_error",
            "pb_9": "project",
        },
    )


def test_query_with_simple_feedback_sort_calls_complete() -> None:
    """Ensure feedback sorting uses calls_complete."""
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_order("feedback.[wandb.runnable.my_op].payload.output.expected", "desc")
    assert_sql(
        cq,
        """
            SELECT
                calls_complete.id AS id
            FROM
                calls_complete
            LEFT JOIN (
                SELECT * FROM feedback WHERE feedback.project_id = {pb_4:String}
            ) AS feedback ON (
                feedback.weave_ref = concat('weave-trace-internal:///',
                {pb_4:String},
                '/call/',
                calls_complete.id))
            PREWHERE
                calls_complete.project_id = {pb_4:String}
            WHERE 1
              AND (
                ((calls_complete.deleted_at IS NULL))
                    AND ((NOT ((calls_complete.started_at IS NULL)))))
            ORDER BY
                (NOT (JSONType(CASE WHEN feedback.feedback_type = {pb_0:String}
                THEN feedback.payload_dump END,
                {pb_1:String},
                {pb_2:String}) = 'Null'
                    OR JSONType(CASE WHEN feedback.feedback_type = {pb_0:String}
                    THEN feedback.payload_dump END,
                    {pb_1:String},
                    {pb_2:String}) IS NULL)) desc,
                toFloat64OrNull(coalesce(nullIf(JSON_VALUE(CASE WHEN feedback.feedback_type = {pb_0:String}
                THEN feedback.payload_dump END,
                {pb_3:String}), 'null'), '')) DESC,
                toString(coalesce(nullIf(JSON_VALUE(CASE WHEN feedback.feedback_type = {pb_0:String}
                THEN feedback.payload_dump END,
                {pb_3:String}), 'null'), '')) DESC
            """,
        {
            "pb_0": "wandb.runnable.my_op",
            "pb_1": "output",
            "pb_2": "expected",
            "pb_3": '$."output"."expected"',
            "pb_4": "project",
        },
    )


def test_calls_complete_with_refs_filter() -> None:
    """Test calls_complete table with input_refs and output_refs filters.

    This test ensures that object ref filtering works correctly with the
    calls_complete table, using direct column access without aggregation.
    """
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
                input_refs=["weave-trace-internal:///project/object/my_input:abc"],
                output_refs=["weave-trace-internal:///project/object/my_output:xyz"],
            )
        )
    )

    assert_sql(
        cq,
        """
        SELECT
            calls_complete.id AS id
        FROM calls_complete
        PREWHERE calls_complete.project_id = {pb_4:String}
        WHERE (((hasAny(calls_complete.input_refs, {pb_2:Array(String)})
                OR length(calls_complete.input_refs) = 0)
            AND (hasAny(calls_complete.output_refs, {pb_3:Array(String)})
                OR length(calls_complete.output_refs) = 0)))
        AND (
            ((calls_complete.deleted_at IS NULL))
            AND ((NOT ((calls_complete.started_at IS NULL))))
            AND (((hasAny(calls_complete.input_refs, {pb_0:Array(String)}))
                AND (hasAny(calls_complete.output_refs, {pb_1:Array(String)}))))
        )
        """,
        {
            "pb_0": ["weave-trace-internal:///project/object/my_input:abc"],
            "pb_1": ["weave-trace-internal:///project/object/my_output:xyz"],
            "pb_2": ["weave-trace-internal:///project/object/my_input:abc"],
            "pb_3": ["weave-trace-internal:///project/object/my_output:xyz"],
            "pb_4": "project",
        },
    )


def test_calls_complete_with_feedback_filter() -> None:
    """Test calls_complete table with feedback filter condition.

    This test ensures that feedback filtering works correctly with the
    calls_complete table, using CASE WHEN for feedback field access while
    using direct column access for calls_complete fields.
    """
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {
                        "$getField": "feedback.[wandb.runnable.my_op].payload.output.score"
                    },
                    {"$literal": 0.5},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT
            calls_complete.id AS id
        FROM
            calls_complete
        LEFT JOIN (
            SELECT * FROM feedback WHERE feedback.project_id = {pb_3:String}
        ) AS feedback ON (
            feedback.weave_ref = concat('weave-trace-internal:///',
            {pb_3:String},
            '/call/',
            calls_complete.id))
        PREWHERE
            calls_complete.project_id = {pb_3:String}
        WHERE 1
          AND (
            ((coalesce(nullIf(JSON_VALUE(CASE WHEN feedback.feedback_type = {pb_0:String}
            THEN feedback.payload_dump END,
            {pb_1:String}), 'null'), '') > {pb_2:Float64}))
            AND ((calls_complete.deleted_at IS NULL))
            AND ((NOT ((calls_complete.started_at IS NULL)))))
        """,
        {
            "pb_0": "wandb.runnable.my_op",
            "pb_1": '$."output"."score"',
            "pb_2": 0.5,
            "pb_3": "project",
        },
    )


def test_query_with_summary_weave_status_filter_calls_complete() -> None:
    """Test that summary.weave.status filter on calls_complete does NOT use aggregate functions.

    This test verifies the fix for the ILLEGAL_AGGREGATION error that occurred when
    filtering by summary.weave.status on the calls_complete table. The calls_complete
    table is pre-aggregated, so queries should NOT use any() aggregate functions.
    """
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")

    # Add a condition to filter for successful or error calls (similar to real usage)
    cq.add_condition(
        tsi_query.OrOperation.model_validate(
            {
                "$or": [
                    {
                        "$eq": [
                            {"$getField": "summary.weave.status"},
                            {"$literal": "success"},
                        ]
                    },
                    {
                        "$eq": [
                            {"$getField": "summary.weave.status"},
                            {"$literal": "error"},
                        ]
                    },
                ]
            }
        )
    )
    assert_sql(
        cq,
        """
        SELECT
            calls_complete.id AS id
        FROM calls_complete PREWHERE calls_complete.project_id = {pb_5:String}
        WHERE 1
          AND (
            (((CASE
                WHEN calls_complete.exception IS NOT NULL THEN {pb_1:String}
                WHEN IFNULL(toInt64OrNull(coalesce(nullIf(JSON_VALUE(calls_complete.summary_dump, {pb_0:String}), 'null'), '')), 0) > 0 THEN {pb_4:String}
                WHEN calls_complete.ended_at IS NULL THEN {pb_2:String}
                ELSE {pb_3:String}
            END = {pb_3:String})
            OR
            (CASE
                WHEN calls_complete.exception IS NOT NULL THEN {pb_1:String}
                WHEN IFNULL(toInt64OrNull(coalesce(nullIf(JSON_VALUE(calls_complete.summary_dump, {pb_0:String}), 'null'), '')), 0) > 0 THEN {pb_4:String}
                WHEN calls_complete.ended_at IS NULL THEN {pb_2:String}
                ELSE {pb_3:String}
            END = {pb_1:String})))
            AND ((calls_complete.deleted_at IS NULL))
            AND ((NOT ((calls_complete.started_at IS NULL)))))
        """,
        {
            "pb_0": '$."status_counts"."error"',
            "pb_1": "error",
            "pb_2": "running",
            "pb_3": "success",
            "pb_4": "descendant_error",
            "pb_5": "project",
        },
    )


def test_build_calls_complete_delete_query() -> None:
    """Ensure the delete helper builds the expected query."""
    query = build_calls_complete_delete_query(
        table_name="calls_complete",
        project_id_param="project_id",
        call_ids_param="call_ids",
    )

    expected = sqlparse.format(
        """
        DELETE FROM calls_complete
        WHERE project_id = {project_id:String} AND id IN {call_ids:Array(String)}
        """,
        reindent=True,
    )

    assert query == expected, f"\nExpected:\n{expected}\n\nGot:\n{query}"


def test_build_calls_complete_delete_query_with_cluster() -> None:
    """Ensure the delete helper builds the expected query with cluster name.

    In distributed mode, mutations target the local table with ON CLUSTER clause.
    """
    query = build_calls_complete_delete_query(
        table_name="calls_complete",
        project_id_param="project_id",
        call_ids_param="call_ids",
        cluster_name="my_cluster",
    )

    expected = sqlparse.format(
        """
        DELETE FROM calls_complete_local ON CLUSTER my_cluster
        WHERE project_id = {project_id:String} AND id IN {call_ids:Array(String)}
        """,
        reindent=True,
    )

    assert query == expected, f"\nExpected:\n{expected}\n\nGot:\n{query}"


def test_build_calls_complete_update_query() -> None:
    """Ensure the update helper builds the expected query."""
    query = build_calls_complete_update_query(
        table_name="calls_complete",
        project_id_param="project_id",
        id_param="id",
        display_name_param="display_name",
    )

    expected = sqlparse.format(
        """
        UPDATE calls_complete
        SET display_name = {display_name:String}
        WHERE project_id = {project_id:String} AND id = {id:String}
        """,
        reindent=True,
    )

    assert query == expected, f"\nExpected:\n{expected}\n\nGot:\n{query}"


def test_build_calls_complete_update_query_with_cluster() -> None:
    """Ensure the update helper builds the expected query with cluster name.

    In distributed mode, mutations target the local table with ON CLUSTER clause.
    """
    query = build_calls_complete_update_query(
        table_name="calls_complete",
        project_id_param="project_id",
        id_param="id",
        display_name_param="display_name",
        cluster_name="my_cluster",
    )

    expected = sqlparse.format(
        """
        UPDATE calls_complete_local ON CLUSTER my_cluster
        SET display_name = {display_name:String}
        WHERE project_id = {project_id:String} AND id = {id:String}
        """,
        reindent=True,
    )

    assert query == expected, f"\nExpected:\n{expected}\n\nGot:\n{query}"


def test_query_with_queue_filter_calls_merged() -> None:
    """Test queue filtering with calls_merged table - should use aggregate functions."""
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "annotation_queue_items.queue_id"},
                    {"$literal": "test_queue_id"},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT
            calls_merged.id AS id
        FROM
            calls_merged
        INNER JOIN (
            SELECT * FROM annotation_queue_items
            WHERE annotation_queue_items.project_id = {pb_1:String}
              AND annotation_queue_items.deleted_at IS NULL
              AND annotation_queue_items.queue_id = {pb_0:String}
        ) AS annotation_queue_items ON (
            annotation_queue_items.project_id = calls_merged.project_id
            AND annotation_queue_items.call_id = calls_merged.id)
        PREWHERE
            calls_merged.project_id = {pb_1:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((any(annotation_queue_items.queue_id) = {pb_0:String}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        """,
        {
            "pb_0": "test_queue_id",
            "pb_1": "project",
        },
    )


def test_query_with_queue_filter_calls_complete() -> None:
    """Test queue filtering with calls_complete table - should NOT use aggregate functions."""
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "annotation_queue_items.queue_id"},
                    {"$literal": "test_queue_id"},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT
            calls_complete.id AS id
        FROM
            calls_complete
        INNER JOIN (
            SELECT * FROM annotation_queue_items
            WHERE annotation_queue_items.project_id = {pb_1:String}
              AND annotation_queue_items.deleted_at IS NULL
              AND annotation_queue_items.queue_id = {pb_0:String}
        ) AS annotation_queue_items ON (
            annotation_queue_items.project_id = calls_complete.project_id
            AND annotation_queue_items.call_id = calls_complete.id)
        PREWHERE
            calls_complete.project_id = {pb_1:String}
        WHERE 1
          AND (
            ((annotation_queue_items.queue_id = {pb_0:String}))
            AND ((calls_complete.deleted_at IS NULL))
            AND ((NOT ((calls_complete.started_at IS NULL)))))
        """,
        {
            "pb_0": "test_queue_id",
            "pb_1": "project",
        },
    )


# -----------------------------------------------------------------------------
# HardCodedFilter.is_useful()
# -----------------------------------------------------------------------------


def test_hardcoded_filter_is_useful_thread_ids_only() -> None:
    """Filter with only thread_ids must be considered useful so set_hardcoded_filter applies it."""
    hcf = HardCodedFilter(filter=tsi.CallsFilter(thread_ids=["thread_1"]))
    assert hcf.is_useful() is True


def test_hardcoded_filter_is_useful_empty_thread_ids_only() -> None:
    """Filter with only thread_ids must be considered useful, even when the list is empty."""
    hcf = HardCodedFilter(filter=tsi.CallsFilter(thread_ids=[]))
    assert hcf.is_useful() is True


def test_hardcoded_filter_is_useful_turn_ids_only() -> None:
    """Filter with only turn_ids must be considered useful."""
    hcf = HardCodedFilter(filter=tsi.CallsFilter(turn_ids=["turn_1"]))
    assert hcf.is_useful() is True


def test_hardcoded_filter_is_useful_empty_not_useful() -> None:
    """Filter with no fields set is not useful."""
    hcf = HardCodedFilter(filter=tsi.CallsFilter())
    assert hcf.is_useful() is False


def test_hardcoded_filter_set_hardcoded_filter_with_thread_ids_only() -> None:
    """set_hardcoded_filter must accept a filter that only has thread_ids (is_useful True)."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.set_hardcoded_filter(HardCodedFilter(filter=tsi.CallsFilter(thread_ids=["t1"])))
    assert cq.hardcoded_filter is not None
    assert cq.hardcoded_filter.filter.thread_ids == ["t1"]


# -----------------------------------------------------------------------------
# _is_minimal_filter()
# -----------------------------------------------------------------------------


def test_is_minimal_filter_none() -> None:
    assert _is_minimal_filter(None) is True


def test_is_minimal_filter_empty() -> None:
    assert _is_minimal_filter(tsi.CallsFilter()) is True


def test_is_minimal_filter_thread_ids_not_minimal() -> None:
    """Filter with thread_ids set must not be considered minimal (optimized path must not apply)."""
    assert _is_minimal_filter(tsi.CallsFilter(thread_ids=["thread_1"])) is False


def test_is_minimal_filter_turn_ids_not_minimal() -> None:
    assert _is_minimal_filter(tsi.CallsFilter(turn_ids=["turn_1"])) is False


def test_is_minimal_filter_wb_user_ids_not_minimal() -> None:
    assert _is_minimal_filter(tsi.CallsFilter(wb_user_ids=["user_1"])) is False


def test_is_minimal_filter_empty_thread_ids_not_minimal() -> None:
    """thread_ids=[] is still a set filter (not None), so not minimal."""
    assert _is_minimal_filter(tsi.CallsFilter(thread_ids=[])) is False


def test_is_minimal_filter_empty_turn_ids_not_minimal() -> None:
    """turn_ids=[] is still a set filter (not None), so not minimal."""
    assert _is_minimal_filter(tsi.CallsFilter(turn_ids=[])) is False


# -----------------------------------------------------------------------------
# build_calls_stats_query() — flat vs subquery shape
# -----------------------------------------------------------------------------


def test_stats_query_calls_complete_flat_count() -> None:
    """Stats query on calls_complete should be flat (no subquery wrapping).

    Fast:  SELECT count() AS count FROM calls_complete PREWHERE ... WHERE ...
    Slow:  SELECT count() FROM (SELECT id FROM calls_complete PREWHERE ... WHERE ...)
    """
    req = tsi.CallsQueryStatsReq(project_id="project")
    assert_stats_sql(
        req,
        """
        SELECT count() AS count
        FROM calls_complete
        PREWHERE calls_complete.project_id = {pb_0:String}
        WHERE 1
          AND (calls_complete.deleted_at IS NULL)
        """,
        {"pb_0": "project"},
        read_table=ReadTable.CALLS_COMPLETE,
    )


def test_stats_query_calls_complete_flat_count_with_filter() -> None:
    """Stats query on calls_complete with hardcoded filter should be flat."""
    req = tsi.CallsQueryStatsReq(
        project_id="project",
        filter=tsi.CallsFilter(op_names=["my_op"]),
    )
    assert_stats_sql(
        req,
        """
        SELECT count() AS count
        FROM calls_complete
        PREWHERE calls_complete.project_id = {pb_1:String}
        WHERE ((calls_complete.op_name IN {pb_0:Array(String)})
               OR (calls_complete.op_name IS NULL))
          AND (calls_complete.deleted_at IS NULL)
        """,
        {"pb_0": ["my_op"], "pb_1": "project"},
        read_table=ReadTable.CALLS_COMPLETE,
    )


def test_stats_query_calls_complete_flat_with_total_storage_size() -> None:
    """Stats query on calls_complete with total_storage_size should be flat with JOIN."""
    req = tsi.CallsQueryStatsReq(
        project_id="project",
        include_total_storage_size=True,
    )
    assert_stats_sql(
        req,
        """
        SELECT count() AS count,
               sum(coalesce(CASE
                   WHEN calls_complete.parent_id IS NULL
                        THEN rolled_up_cms.total_storage_size_bytes
                   ELSE NULL
               END, 0)) AS total_storage_size_bytes
        FROM calls_complete
        LEFT JOIN (
            SELECT trace_id,
                   sum(COALESCE(attributes_size_bytes,0) + COALESCE(inputs_size_bytes,0) + COALESCE(output_size_bytes,0) + COALESCE(summary_size_bytes,0)) AS total_storage_size_bytes
            FROM calls_complete_stats
            WHERE project_id = {pb_0:String}
            GROUP BY trace_id
        ) AS rolled_up_cms ON calls_complete.trace_id = rolled_up_cms.trace_id
        PREWHERE calls_complete.project_id = {pb_0:String}
        WHERE 1
          AND (calls_complete.deleted_at IS NULL)
        """,
        {"pb_0": "project"},
        read_table=ReadTable.CALLS_COMPLETE,
    )


def test_stats_query_calls_merged_uses_subquery() -> None:
    """Stats query on calls_merged should use subquery wrapping (GROUP BY requires it)."""
    req = tsi.CallsQueryStatsReq(project_id="project")
    assert_stats_sql(
        req,
        """
        SELECT count()
        FROM (
            SELECT calls_merged.id AS id
            FROM calls_merged
            PREWHERE calls_merged.project_id = {pb_0:String}
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((any(calls_merged.deleted_at) IS NULL))
                AND
                ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
        )
        """,
        {"pb_0": "project"},
        read_table=ReadTable.CALLS_MERGED,
    )
