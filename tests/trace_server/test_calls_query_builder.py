import pytest
import sqlparse

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import (
    AggregatedDataSizeField,
    CallsQuery,
    HardCodedFilter,
)
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
        WHERE calls_merged.project_id = {pb_0:String}
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
        WHERE calls_merged.project_id = {pb_0:String}
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
        WHERE calls_merged.project_id = {pb_0:String}
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
            WHERE calls_merged.project_id = {pb_1:String}
                AND ((calls_merged.op_name IN {pb_0:Array(String)})
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
        WHERE
            calls_merged.project_id = {pb_1:String}
        AND
            (calls_merged.id IN filtered_calls)
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
            WHERE calls_merged.project_id = {pb_1:String}
                AND ((calls_merged.op_name IN {pb_0:Array(String)})
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
        WHERE
            calls_merged.project_id = {pb_1:String}
        AND
            (calls_merged.id IN filtered_calls)
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
            WHERE calls_merged.project_id = {pb_1:String}
                AND ((calls_merged.op_name IN {pb_0:Array(String)})
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
        WHERE
            calls_merged.project_id = {pb_1:String}
        AND
            (calls_merged.id IN filtered_calls)
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
            WHERE calls_merged.project_id = {pb_2:String}
                AND ((calls_merged.op_name IN {pb_1:Array(String)})
                    OR (calls_merged.op_name IS NULL))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((any(calls_merged.wb_user_id) = {pb_0:String}))
            AND
                ((any(calls_merged.deleted_at) IS NULL))
            AND
                ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        WHERE
            calls_merged.project_id = {pb_2:String}
        AND (calls_merged.id IN filtered_calls)
        AND ((calls_merged.inputs_dump LIKE {pb_7:String} OR calls_merged.inputs_dump IS NULL)
            AND (calls_merged.inputs_dump LIKE {pb_8:String} OR calls_merged.inputs_dump IS NULL))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((JSON_VALUE(any(calls_merged.inputs_dump), {pb_3:String}) = {pb_4:String}))
            AND
            ((JSON_VALUE(any(calls_merged.inputs_dump), {pb_5:String}) = {pb_6:String}))
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
            "pb_5": '$."param"."bool"',
            "pb_6": "true",
            "pb_7": '%"hello"%',
            "pb_8": "%true%",
        },
    )


def assert_sql(cq: CallsQuery, exp_query, exp_params):
    pb = ParamBuilder("pb")
    query = cq.as_sql(pb)
    params = pb.get_params()

    exp_formatted = sqlparse.format(exp_query, reindent=True)
    found_formatted = sqlparse.format(query, reindent=True)

    assert exp_formatted == found_formatted
    assert exp_params == params


def test_query_light_column_with_costs() -> None:
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
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
        WITH
            filtered_calls AS (
                SELECT calls_merged.id AS id
                FROM calls_merged
                WHERE calls_merged.project_id = {pb_1:String}
                    AND ((calls_merged.op_name IN {pb_0:Array(String)})
                        OR (calls_merged.op_name IS NULL))
                GROUP BY (calls_merged.project_id, calls_merged.id)
                HAVING (((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
                )
            ),
            all_calls AS (
                SELECT
                    calls_merged.id AS id,
                    any(calls_merged.started_at) AS started_at
                FROM calls_merged
                WHERE calls_merged.project_id = {pb_1:String}
                    AND (calls_merged.id IN filtered_calls)
                GROUP BY (calls_merged.project_id, calls_merged.id)),
            -- From the all_calls we get the usage data for LLMs
            llm_usage AS (
                SELECT
                    *,
                    ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                    arrayJoin(
                        if(usage_raw != '',
                        JSONExtractKeysAndValuesRaw(usage_raw),
                        [('weave_dummy_llm_id', '{"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}')])
                    ) AS kv,
                    kv.1 AS llm_id,
                    JSONExtractInt(kv.2, 'requests') AS requests,
                    if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens,
                    if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens,
                    JSONExtractInt(kv.2, 'total_tokens') AS total_tokens
                FROM all_calls),
            -- based on the llm_ids in the usage data we get all the prices and rank them according to specificity and effective date
            ranked_prices AS (
                SELECT
                    *,
                    llm_token_prices.id,
                    llm_token_prices.pricing_level,
                    llm_token_prices.pricing_level_id,
                    llm_token_prices.provider_id,
                    llm_token_prices.llm_id,
                    llm_token_prices.effective_date,
                    llm_token_prices.prompt_token_cost,
                    llm_token_prices.completion_token_cost,
                    llm_token_prices.prompt_token_cost_unit,
                    llm_token_prices.completion_token_cost_unit,
                    llm_token_prices.created_by,
                    llm_token_prices.created_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY llm_usage.id, llm_usage.llm_id
                        ORDER BY
                            CASE
                                -- Order by effective_date
                                WHEN llm_usage.started_at >= llm_token_prices.effective_date THEN 1
                                ELSE 2
                            END,
                            CASE
                                -- Order by pricing level then by effective_date
                                -- WHEN llm_token_prices.pricing_level = 'org' AND llm_token_prices.pricing_level_id = ORG_PARAM THEN 1
                                WHEN llm_token_prices.pricing_level = 'project' AND llm_token_prices.pricing_level_id = 'UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=' THEN 2
                                WHEN llm_token_prices.pricing_level = 'default' AND llm_token_prices.pricing_level_id = 'default' THEN 3
                                ELSE 4
                            END,
                            llm_token_prices.effective_date DESC
                    ) AS rank
                FROM llm_usage
                LEFT JOIN llm_token_prices ON (llm_usage.llm_id = llm_token_prices.llm_id)
                WHERE ((llm_token_prices.pricing_level_id = {pb_2:String})
                    OR (llm_token_prices.pricing_level_id = {pb_3:String})
                    OR (llm_token_prices.pricing_level_id = {pb_4:String})))
            -- Final Select, which just selects the correct fields, and adds a costs object
            SELECT
                id,
                started_at,
                if( any(llm_id) = 'weave_dummy_llm_id',
                any(summary_dump),
                concat(
                    left(any(summary_dump), length(any(summary_dump)) - 1),
                    ',"weave":{',
                        '"costs":',
                        concat(
                            '{',
                            arrayStringConcat(
                                groupUniqArray(
                                    concat(
                                        '"', toString(llm_id), '":{',
                                        '"prompt_tokens":', toString(prompt_tokens), ',',
                                        '"completion_tokens":', toString(completion_tokens), ',',
                                        '"requests":', toString(requests), ',',
                                        '"total_tokens":', toString(total_tokens), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',',
                                        '"completion_token_cost":', toString(completion_token_cost), ',',
                                        '"prompt_tokens_total_cost":', toString(prompt_tokens * prompt_token_cost), ',',
                                        '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',',
                                        '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit),  '",',
                                        '"completion_token_cost_unit":"', toString(completion_token_cost_unit),  '",',
                                        '"effective_date":"', toString(effective_date),  '",',
                                        '"provider_id":"', toString(provider_id),  '",',
                                        '"pricing_level":"', toString(pricing_level),  '",',
                                        '"pricing_level_id":"', toString(pricing_level_id),  '",',
                                        '"created_by":"', toString(created_by),  '",',
                                        '"created_at":"', toString(created_at),
                                    '"}'
                                    )
                                ), ','
                            ),
                            '} }'
                        ),
                    '}' )
                ) AS summary_dump
            FROM ranked_prices
            WHERE (rank = {pb_5:UInt64})
            GROUP BY id, started_at
        """,
        {
            "pb_0": ["a", "b"],
            "pb_1": "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
            "pb_2": "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
            "pb_3": "default",
            "pb_4": "",
            "pb_5": 1,
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
        LEFT JOIN feedback ON
            (feedback.weave_ref = concat('weave-trace-internal:///',
            {pb_4:String},
            '/call/',
            calls_merged.id))
        WHERE
            calls_merged.project_id = {pb_4:String}
            AND calls_merged.project_id = {pb_4:String}
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
            toFloat64OrNull(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_0:String}),
            {pb_3:String})) DESC,
            toString(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_0:String}),
            {pb_3:String})) DESC
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
        WHERE
            calls_merged.project_id = {pb_1:String}
            AND ((calls_merged.op_name IN {pb_0:Array(String)})
                OR (calls_merged.op_name IS NULL))
        GROUP BY
            (calls_merged.project_id,
            calls_merged.id)
        HAVING
            (((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            ))
        SELECT
            calls_merged.id AS id
        FROM
            calls_merged
        LEFT JOIN feedback ON
            (feedback.weave_ref = concat('weave-trace-internal:///',
            {pb_1:String},
            '/call/',
            calls_merged.id))
        WHERE
            calls_merged.project_id = {pb_1:String}
            AND calls_merged.project_id = {pb_1:String}
            AND (calls_merged.id IN filtered_calls)
        GROUP BY
            (calls_merged.project_id,
            calls_merged.id)
        ORDER BY
            (NOT (JSONType(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_2:String}),
            {pb_3:String},
            {pb_4:String}) = 'Null'
                OR JSONType(anyIf(feedback.payload_dump,
                feedback.feedback_type = {pb_2:String}),
                {pb_3:String},
                {pb_4:String}) IS NULL)) desc,
            toFloat64OrNull(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_2:String}),
            {pb_5:String})) DESC,
            toString(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_2:String}),
            {pb_5:String})) DESC
        """,
        {
            "pb_0": ["weave-trace-internal:///project/op/my_op:1234567890"],
            "pb_1": "project",
            "pb_2": "wandb.runnable.my_op",
            "pb_3": "output",
            "pb_4": "expected",
            "pb_5": '$."output"."expected"',
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
        LEFT JOIN feedback ON
            (feedback.weave_ref = concat('weave-trace-internal:///',
            {pb_3:String},
            '/call/',
            calls_merged.id))
        WHERE
            calls_merged.project_id = {pb_3:String}
            AND calls_merged.project_id = {pb_3:String}
        GROUP BY
            (calls_merged.project_id,
            calls_merged.id)
        HAVING
            (((JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_0:String}),
            {pb_1:String}) > JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_0:String}),
            {pb_2:String})))
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
        LEFT JOIN feedback ON
            (feedback.weave_ref = concat('weave-trace-internal:///',
            {pb_6:String},
            '/call/',
            calls_merged.id))
        WHERE
            calls_merged.project_id = {pb_6:String}
            AND calls_merged.project_id = {pb_6:String}
        GROUP BY
            (calls_merged.project_id,
            calls_merged.id)
        HAVING
            (((JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_0:String}),
            {pb_1:String}) = {pb_2:String}))
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
            toFloat64OrNull(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_0:String}),
            {pb_5:String})) DESC,
            toString(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_0:String}),
            {pb_5:String})) DESC
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
        WHERE calls_merged.project_id = {pb_0:String}
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
            WHERE calls_merged.project_id = {pb_1:String}
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((any(calls_merged.wb_user_id) = {pb_0:String}))
                AND ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        WHERE
            calls_merged.project_id = {pb_1:String}
        AND
            (calls_merged.id IN filtered_calls)
        AND
            ((calls_merged.inputs_dump LIKE {pb_4:String} OR calls_merged.inputs_dump IS NULL))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            JSON_VALUE(any(calls_merged.inputs_dump), {pb_2:String}) = {pb_3:String}
        )
        """,
        {
            "pb_0": "my_user_id",
            "pb_1": "project",
            "pb_2": '$."param"."val"',
            "pb_3": "hello",
            "pb_4": '%"hello"%',
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
        WHERE calls_merged.project_id = {pb_3:String}
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
            WHEN any(calls_merged.exception) IS NOT NULL THEN {pb_0:String}
            WHEN any(calls_merged.ended_at) IS NULL THEN {pb_1:String}
            ELSE {pb_2:String}
        END ASC
        """,
        {"pb_0": "error", "pb_1": "running", "pb_2": "success", "pb_3": "project"},
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
        WHERE calls_merged.project_id = {pb_3:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((CASE
                WHEN any(calls_merged.exception) IS NOT NULL THEN {pb_0:String}
                WHEN any(calls_merged.ended_at) IS NULL THEN {pb_1:String}
                ELSE {pb_2:String}
            END = {pb_2:String}))
        AND ((any(calls_merged.deleted_at) IS NULL))
        AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        ORDER BY CASE
            WHEN any(calls_merged.exception) IS NOT NULL THEN {pb_0:String}
            WHEN any(calls_merged.ended_at) IS NULL THEN {pb_1:String}
            ELSE {pb_2:String}
        END DESC
        """,
        {
            "pb_0": "error",
            "pb_1": "running",
            "pb_2": "success",
            "pb_3": "project",
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
            WHERE calls_merged.project_id = {pb_1:String}
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((any(calls_merged.wb_user_id) = {pb_0:String}))
                AND ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump,
            any(calls_merged.output_dump) AS output_dump
        FROM calls_merged
        WHERE
            calls_merged.project_id = {pb_1:String}
        AND (calls_merged.id IN filtered_calls)
        AND ((calls_merged.inputs_dump LIKE {pb_6:String} OR calls_merged.inputs_dump IS NULL)
            AND (calls_merged.output_dump LIKE {pb_7:String} OR calls_merged.output_dump IS NULL))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((JSON_VALUE(any(calls_merged.inputs_dump), {pb_2:String}) = {pb_3:String}))
            AND
            ((JSON_VALUE(any(calls_merged.output_dump), {pb_4:String}) = {pb_5:String}))
        )
        """,
        {
            "pb_0": "my_user_id",
            "pb_1": "project",
            "pb_2": '$."param"."val"',
            "pb_3": "hello",
            "pb_4": '$."result"',
            "pb_5": "success",
            "pb_6": '%"hello"%',
            "pb_7": '%"success"%',
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
        WHERE calls_merged.project_id = {pb_6:String}
            AND (((calls_merged.inputs_dump LIKE {pb_4:String} OR calls_merged.inputs_dump IS NULL)
                OR (calls_merged.output_dump LIKE {pb_5:String} OR calls_merged.output_dump IS NULL)))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING ((
            ((JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}) = {pb_1:String})
            OR
            (JSON_VALUE(any(calls_merged.output_dump), {pb_2:String}) = {pb_3:String})))
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
            WHERE calls_merged.project_id = {pb_1:String}
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((any(calls_merged.wb_user_id) = {pb_0:String}))
                AND ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump,
            any(calls_merged.output_dump) AS output_dump
        FROM calls_merged
        WHERE
            calls_merged.project_id = {pb_1:String}
          AND (calls_merged.id IN filtered_calls)
          AND (
            (calls_merged.inputs_dump LIKE {pb_10:String} OR calls_merged.inputs_dump IS NULL)
            AND ((calls_merged.output_dump LIKE {pb_11:String} OR calls_merged.output_dump IS NULL)
                OR (lower(calls_merged.inputs_dump) LIKE {pb_12:String} OR calls_merged.inputs_dump IS NULL)))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((JSON_VALUE(any(calls_merged.inputs_dump), {pb_2:String}) = {pb_3:String}))
            AND
            ((JSON_VALUE(any(calls_merged.inputs_dump), {pb_4:String}) > {pb_5:UInt64}))
            AND (((JSON_VALUE(any(calls_merged.output_dump), {pb_6:String}) = {pb_7:String})
              OR positionCaseInsensitive(JSON_VALUE(any(calls_merged.inputs_dump), {pb_8:String}), {pb_9:String}) > 0))
        )
        """,
        {
            "pb_0": "my_user_id",
            "pb_1": "project",
            "pb_2": '$."param"."val"',
            "pb_3": "hello",
            "pb_4": '$."param"."count"',
            "pb_5": 5,
            "pb_6": '$."result"."status"',
            "pb_7": "success",
            "pb_8": '$."param"."message"',
            "pb_9": "completed",
            "pb_10": '%"hello"%',
            "pb_11": '%"success"%',
            "pb_12": '%"%completed%"%',
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
        WHERE
            calls_merged.project_id = {pb_3:String}
        AND
            ((calls_merged.inputs_dump LIKE {pb_2:String} OR calls_merged.inputs_dump IS NULL))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}) = {pb_1:String}))
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
        WHERE
            calls_merged.project_id = {pb_3:String}
        AND
            ((lower(calls_merged.inputs_dump) LIKE {pb_2:String} OR calls_merged.inputs_dump IS NULL))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            (positionCaseInsensitive(JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}), {pb_1:String}) > 0)
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
        WHERE
            calls_merged.project_id = {pb_5:String}
        AND
            (((calls_merged.inputs_dump LIKE {pb_3:String} OR calls_merged.inputs_dump LIKE {pb_4:String})
                OR calls_merged.inputs_dump IS NULL))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}) IN ({pb_1:String},{pb_2:String})))
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
            WHERE calls_merged.project_id = {pb_1:String}
                AND ((calls_merged.op_name IN {pb_0:Array(String)})
                    OR (calls_merged.op_name IS NULL))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.attributes_dump) AS attributes_dump,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        WHERE
            calls_merged.project_id = {pb_1:String}
        AND
            (calls_merged.id IN filtered_calls)
            AND ((calls_merged.attributes_dump LIKE {pb_9:String} OR calls_merged.attributes_dump IS NULL)
            AND (lower(calls_merged.inputs_dump) LIKE {pb_10:String} OR calls_merged.inputs_dump IS NULL)
            AND ((calls_merged.attributes_dump LIKE {pb_11:String} OR calls_merged.attributes_dump LIKE {pb_12:String})
                OR calls_merged.attributes_dump IS NULL))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((JSON_VALUE(any(calls_merged.attributes_dump), {pb_2:String}) = {pb_3:String}))
            AND
            (positionCaseInsensitive(JSON_VALUE(any(calls_merged.inputs_dump), {pb_4:String}), {pb_5:String}) > 0)
            AND
            ((JSON_VALUE(any(calls_merged.attributes_dump), {pb_6:String}) IN ({pb_7:String},{pb_8:String})))
        )
        """,
        {
            "pb_0": ["llm/openai", "llm/anthropic"],
            "pb_1": "project",
            "pb_2": '$."model"',
            "pb_3": "gpt-4",
            "pb_4": '$."prompt"',
            "pb_5": "weather",
            "pb_6": '$."temperature"',
            "pb_7": "0.7",
            "pb_8": "0.8",
            "pb_9": '%"gpt-4"%',
            "pb_10": '%"%weather%"%',
            "pb_11": '%"0.7"%',
            "pb_12": '%"0.8"%',
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
        WHERE
            calls_merged.project_id = {pb_5:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (((
            (JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}) = {pb_1:String})
            OR (JSON_VALUE(any(calls_merged.inputs_dump), {pb_2:String}) > {pb_3:UInt64})))
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
        WHERE calls_merged.project_id = {pb_2:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}) = {pb_1:String}))
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
        WHERE calls_merged.project_id = {pb_0:String}
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
        WHERE calls_merged.project_id = {pb_1:String}
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
        WHERE calls_merged.project_id = {pb_0:String}
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
        WHERE calls_merged.project_id = {pb_1:String}
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


def test_storage_size_fields():
    """Test querying with storage size fields"""
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
                sum(COALESCE(attributes_size_bytes, 0) + COALESCE(inputs_size_bytes, 0) + COALESCE(output_size_bytes, 0) + COALESCE(summary_size_bytes, 0)) as storage_size_bytes
        FROM calls_merged_stats
        WHERE project_id = {pb_0:String}
        GROUP BY id) as storage_size_tbl on calls_merged.id = storage_size_tbl.id
        WHERE calls_merged.project_id = {pb_0:String}
        GROUP BY (calls_merged.project_id,
                calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        """,
        {"pb_0": "test/project"},
    )


def test_total_storage_size():
    """Test querying with total storage size"""
    cq = CallsQuery(project_id="test/project", include_total_storage_size=True)
    cq.add_field("id")
    cq.add_field("total_storage_size_bytes")

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
            sum(COALESCE(attributes_size_bytes,0) + COALESCE(inputs_size_bytes,0) + COALESCE(output_size_bytes,0) + COALESCE(summary_size_bytes,0)) as total_storage_size_bytes
        FROM calls_merged_stats
        WHERE project_id = {pb_0:String}
        GROUP BY trace_id) as rolled_up_cms
        on calls_merged.trace_id = rolled_up_cms.trace_id
        WHERE calls_merged.project_id = {pb_0:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": "test/project"},
    )


def test_aggregated_data_size_field():
    """Test the AggregatedDataSizeField class"""
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
        WHERE calls_merged.project_id = {pb_2:String}
            AND (calls_merged.sortable_datetime > {pb_1:String})
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
        WHERE calls_merged.project_id = {pb_2:String}
            AND (NOT (calls_merged.sortable_datetime >= {pb_1:String}))
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
        WHERE calls_merged.project_id = {pb_4:String}
            AND (calls_merged.sortable_datetime > {pb_2:String}
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
        WHERE calls_merged.project_id = {pb_2:String}
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
            WHERE calls_merged.project_id = {pb_2:String}
                AND (calls_merged.sortable_datetime > {pb_1:String})
            GROUP BY (calls_merged.project_id,
                        calls_merged.id)
            HAVING (((any(calls_merged.started_at) > {pb_0:UInt64}))
                    AND ((any(calls_merged.deleted_at) IS NULL))
                    AND ((NOT ((any(calls_merged.started_at) IS NULL))))))
        SELECT calls_merged.id AS id
        FROM calls_merged
        LEFT JOIN feedback ON (feedback.weave_ref = concat('weave-trace-internal:///', {pb_2:String}, '/call/', calls_merged.id))
        WHERE calls_merged.project_id = {pb_2:String}
            AND calls_merged.project_id = {pb_2:String}
            AND (calls_merged.id IN filtered_calls)
            AND ((calls_merged.inputs_dump LIKE {pb_8:String}
                OR calls_merged.inputs_dump IS NULL))
        GROUP BY (calls_merged.project_id,
                calls_merged.id)
        HAVING (((JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_3:String}), {pb_4:String}) > JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_3:String}), {pb_5:String})))
            AND ((JSON_VALUE(any(calls_merged.inputs_dump), {pb_6:String}) = {pb_7:String})))
        """,
        {
            "pb_0": 1709251200,
            "pb_1": "2024-02-29 23:55:00.000000",
            "pb_2": "project",
            "pb_3": "wandb.runnable.my_op",
            "pb_4": '$."output"."expected"',
            "pb_5": '$."output"."found"',
            "pb_6": '$."message"',
            "pb_7": "hello",
            "pb_8": '%"hello"%',
        },
    )


def test_filter_length_validation():
    """Test that filter length validation works"""
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
