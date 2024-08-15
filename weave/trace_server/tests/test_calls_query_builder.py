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


def test_query_light_column_with_costs() -> None:
    cq = CallsQuery(project_id="project", include_costs=True)
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
            filtered_calls AS
                (SELECT calls_merged.id AS id
                FROM calls_merged
                WHERE project_id = {pb_1:String}
                GROUP BY (project_id,
                            id)
                HAVING (
                    ((any(calls_merged.deleted_at) IS NULL))
                AND
                    (any(calls_merged.op_name) IN {pb_0:Array(String)})
                )),
            all_calls AS
                (SELECT calls_merged.id AS id,
                        any(calls_merged.started_at) AS started_at
                FROM calls_merged
                WHERE project_id = {pb_2:String}
                    AND (id IN filtered_calls)
                GROUP BY (project_id,
                            id)), -- From the all_calls we get the usage data for LLMs
            llm_usage AS
                (SELECT id,
                        started_at,
                        ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                        arrayJoin(JSONExtractKeysAndValuesRaw(usage_raw)) AS kv,
                        kv.1 AS llm_id,
                        JSONExtractInt(kv.2, 'requests') AS requests,
                        if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens,
                        if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens,
                        JSONExtractInt(kv.2, 'total_tokens') AS total_tokens
                FROM all_calls
                WHERE (NOT ((usage_raw = {pb_3:String})))), -- based on the llm_ids in the usage data we get all the prices and rank them according to specificity and effective date
            ranked_prices AS
                (SELECT llm_usage.id,
                        llm_usage.llm_id,
                        llm_usage.requests,
                        llm_usage.prompt_tokens,
                        llm_usage.completion_tokens,
                        llm_usage.total_tokens,
                        llm_usage.started_at,
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
                        ROW_NUMBER() OVER (PARTITION BY llm_usage.id, llm_usage.llm_id
                            ORDER BY CASE -- Order by pricing level then by effective_date
                                -- WHEN llm_token_prices.pricing_level = 'org' AND llm_token_prices.pricing_level_id = ORG_NAME THEN 1
                                WHEN llm_token_prices.pricing_level = 'project'
                                    AND llm_token_prices.pricing_level_id = 'project' THEN 2
                                WHEN llm_token_prices.pricing_level = 'default'
                                    AND llm_token_prices.pricing_level_id = 'default' THEN 3
                                ELSE 4
                            END, llm_token_prices.effective_date DESC) AS rank
                FROM llm_usage
                LEFT JOIN llm_token_prices ON (llm_usage.llm_id = llm_token_prices.llm_id)
                WHERE (llm_usage.started_at >= llm_token_prices.effective_date)), -- Discard all but the top-ranked prices for each llm_id and call id
            top_ranked_prices AS
                (SELECT id,
                        pricing_level,
                        pricing_level_id,
                        provider_id,
                        llm_id,
                        effective_date,
                        prompt_token_cost,
                        completion_token_cost,
                        prompt_token_cost_unit,
                        completion_token_cost_unit,
                        created_by,
                        created_at
                FROM ranked_prices
                WHERE (rank = {pb_4:UInt64})), -- Join with the top-ranked prices to get the token costs
            usage_with_costs AS
                (SELECT llm_usage.id,
                        llm_usage.llm_id,
                        llm_usage.requests,
                        llm_usage.prompt_tokens,
                        llm_usage.completion_tokens,
                        llm_usage.total_tokens,
                        top_ranked_prices.pricing_level,
                        top_ranked_prices.pricing_level_id,
                        top_ranked_prices.provider_id,
                        top_ranked_prices.llm_id,
                        top_ranked_prices.effective_date,
                        top_ranked_prices.prompt_token_cost,
                        top_ranked_prices.completion_token_cost,
                        top_ranked_prices.prompt_token_cost_unit,
                        top_ranked_prices.completion_token_cost_unit,
                        top_ranked_prices.created_by,
                        top_ranked_prices.created_at,
                        prompt_tokens * prompt_token_cost AS prompt_tokens_cost,
                        completion_tokens * completion_token_cost AS completion_tokens_cost
                FROM llm_usage
                LEFT JOIN top_ranked_prices ON ((llm_usage.id = top_ranked_prices.id) AND (llm_usage.llm_id = top_ranked_prices.llm_id)))
        -- Final Select, which just pulls all the data from all_calls, and adds a costs object
        SELECT all_calls.id,
            all_calls.started_at,
            concat(left(any(all_calls.summary_dump), length(any(all_calls.summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',', '"prompt_tokens_cost":', toString(prompt_tokens_cost), ',', '"completion_tokens_cost":', toString(completion_tokens_cost), ',', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }'), '}') AS summary_dump
        FROM all_calls
        JOIN usage_with_costs ON (all_calls.id = usage_with_costs.id)
        GROUP BY all_calls.id,
                all_calls.started_at
        """,
        {
            "pb_0": ["a", "b"],
            "pb_1": "project",
            "pb_2": "project",
            "pb_3": "{}",
            "pb_4": 1,
        },
    )
