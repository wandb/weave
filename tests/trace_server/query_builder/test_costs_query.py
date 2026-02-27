from tests.trace_server.query_builder.utils import assert_sql
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
)


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
                PREWHERE calls_merged.project_id = {pb_1:String}
                WHERE ((calls_merged.op_name IN {pb_0:Array(String)})
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
                PREWHERE calls_merged.project_id = {pb_1:String}
                WHERE (calls_merged.id IN filtered_calls)
                GROUP BY (calls_merged.project_id, calls_merged.id)),
            llm_usage AS (
                -- From the all_calls we get the usage data for LLMs
                SELECT
                    *,
                    ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                    arrayJoin(
                        if(
                            usage_raw != '' and usage_raw != '{}',
                            JSONExtractKeysAndValuesRaw(usage_raw),
                            [('weave_dummy_llm_id', '{\\"requests\\": 0, \\"prompt_tokens\\": 0, \\"completion_tokens\\": 0, \\"total_tokens\\": 0}')]
                        )
                    ) AS kv,
                    kv.1 AS llm_id,
                    JSONExtractInt(kv.2, 'requests') AS requests,
                    (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0)) AS prompt_tokens,
                    (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0) + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0)) AS completion_tokens,
                    JSONExtractInt(kv.2, 'total_tokens') AS total_tokens
                FROM all_calls),
            ranked_prices AS (
                -- based on the llm_ids in the usage data we get all the prices and rank them according to specificity and effective date
                SELECT
                    *,
                    llm_token_prices.id,
                    llm_token_prices.pricing_level,
                    llm_token_prices.pricing_level_id,
                    llm_token_prices.provider_id,
                    llm_token_prices.llm_id,
                    llm_token_prices.effective_date,
                    llm_token_prices.prompt_token_cost,
                    llm_token_prices.cached_prompt_token_cost,
                    llm_token_prices.completion_token_cost,
                    llm_token_prices.prompt_token_cost_unit,
                    llm_token_prices.cached_prompt_token_cost_unit,
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
                LEFT JOIN llm_token_prices ON ((llm_usage.llm_id = llm_token_prices.llm_id) AND ((llm_token_prices.pricing_level_id = {pb_2:String})
                    OR (llm_token_prices.pricing_level_id = {pb_3:String})
                    OR (llm_token_prices.pricing_level_id = {pb_4:String}))) )
            -- Final Select, which just selects the correct fields, and adds a costs object
            SELECT
                id,
                started_at,
                if( any(llm_id) = 'weave_dummy_llm_id' or any(llm_token_prices.id) == '',
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
                                        '"cached_prompt_tokens":', toString(least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens)), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',',
                                        '"cached_prompt_token_cost":', toString(cached_prompt_token_cost), ',',
                                        '"completion_token_cost":', toString(completion_token_cost), ',',
                                        '"prompt_tokens_total_cost":', toString((greatest(prompt_tokens - least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens), 0) * prompt_token_cost) + (least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens) * cached_prompt_token_cost)), ',',
                                        '"cached_prompt_tokens_total_cost":', toString(least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens) * cached_prompt_token_cost), ',',
                                        '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',',
                                        '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit),  '",',
                                        '"cached_prompt_token_cost_unit":"', toString(cached_prompt_token_cost_unit),  '",',
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


def test_query_with_costs_and_attributes_order() -> None:
    """Test ordering by attributes_dump field when costs are enabled.

    This test verifies the fix for the issue where ordering by attributes_dump
    would fail because the field wasn't being selected in the all_calls CTE
    and wasn't propagated through to the final query.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("attributes_dump", "ASC")

    assert_sql(
        cq,
        """
        WITH filtered_calls AS
            (SELECT calls_merged.id AS id
             FROM calls_merged
             PREWHERE calls_merged.project_id = {pb_0:String}
             GROUP BY (calls_merged.project_id,
                       calls_merged.id)
             HAVING (((any(calls_merged.deleted_at) IS NULL))
                     AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
             ORDER BY (NOT (JSONType(any(calls_merged.attributes_dump)) = 'Null'
                            OR JSONType(any(calls_merged.attributes_dump)) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), '$'), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), '$'), 'null'), '')) ASC),
             all_calls AS
            (SELECT calls_merged.id AS id,
                    any(calls_merged.started_at) AS started_at,
                    any(calls_merged.attributes_dump) AS attributes_dump
             FROM calls_merged
             PREWHERE calls_merged.project_id = {pb_0:String}
             WHERE (calls_merged.id IN filtered_calls)
             GROUP BY (calls_merged.project_id,
                       calls_merged.id)
             ORDER BY (NOT (JSONType(any(calls_merged.attributes_dump)) = 'Null'
                            OR JSONType(any(calls_merged.attributes_dump)) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), '$'), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), '$'), 'null'), '')) ASC),
             llm_usage AS
            (-- From the all_calls we get the usage data for LLMs
             SELECT *,
                    ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                    arrayJoin(if(usage_raw != ''
                                 and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\\"requests\\": 0, \\"prompt_tokens\\": 0, \\"completion_tokens\\": 0, \\"total_tokens\\": 0}')])) AS kv,
                    kv.1 AS llm_id,
                    JSONExtractInt(kv.2, 'requests') AS requests,
                    (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0)) AS prompt_tokens,
                    (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0) + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0)) AS completion_tokens,
                    JSONExtractInt(kv.2, 'total_tokens') AS total_tokens
             FROM all_calls),
             ranked_prices AS
            (-- based on the llm_ids in the usage data we get all the prices and rank them according to specificity and effective date
             SELECT *,
                    llm_token_prices.id,
                    llm_token_prices.pricing_level,
                    llm_token_prices.pricing_level_id,
                    llm_token_prices.provider_id,
                    llm_token_prices.llm_id,
                    llm_token_prices.effective_date,
                    llm_token_prices.prompt_token_cost,
                    llm_token_prices.cached_prompt_token_cost,
                    llm_token_prices.completion_token_cost,
                    llm_token_prices.prompt_token_cost_unit,
                    llm_token_prices.cached_prompt_token_cost_unit,
                    llm_token_prices.completion_token_cost_unit,
                    llm_token_prices.created_by,
                    llm_token_prices.created_at,
                    ROW_NUMBER() OVER (PARTITION BY llm_usage.id, llm_usage.llm_id
                                       ORDER BY CASE -- Order by effective_date
                                                    WHEN llm_usage.started_at >= llm_token_prices.effective_date THEN 1
                                                    ELSE 2
                                                END, CASE -- Order by pricing level then by effective_date
                                                     -- WHEN llm_token_prices.pricing_level = 'org' AND llm_token_prices.pricing_level_id = ORG_PARAM THEN 1
                                                         WHEN llm_token_prices.pricing_level = 'project'
                                                              AND llm_token_prices.pricing_level_id = 'UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=' THEN 2
                                                         WHEN llm_token_prices.pricing_level = 'default'
                                                              AND llm_token_prices.pricing_level_id = 'default' THEN 3
                                                         ELSE 4
                                                     END, llm_token_prices.effective_date DESC) AS rank
             FROM llm_usage
             LEFT JOIN llm_token_prices ON ((llm_usage.llm_id = llm_token_prices.llm_id)
                                            AND ((llm_token_prices.pricing_level_id = {pb_1:String})
                                                 OR (llm_token_prices.pricing_level_id = {pb_2:String})
                                                 OR (llm_token_prices.pricing_level_id = {pb_3:String})))) -- Final Select, which just selects the correct fields, and adds a costs object
        SELECT id,
               started_at,
               attributes_dump,
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"cached_prompt_tokens":', toString(least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens)), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',', '"cached_prompt_token_cost":', toString(cached_prompt_token_cost), ',',
                                        '"completion_token_cost":', toString(completion_token_cost), ',', '"prompt_tokens_total_cost":', toString((greatest(prompt_tokens - least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens), 0) * prompt_token_cost) + (least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens) * cached_prompt_token_cost)), ',',
                                        '"cached_prompt_tokens_total_cost":', toString(least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens) * cached_prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit),  '",',
                                        '"cached_prompt_token_cost_unit":"', toString(cached_prompt_token_cost_unit),  '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_4:UInt64})
        GROUP BY id,
                 started_at,
                 attributes_dump
            ORDER BY (NOT (JSONType(any(ranked_prices.attributes_dump)) = 'Null'
                           OR JSONType(any(ranked_prices.attributes_dump)) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(ranked_prices.attributes_dump), '$'), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(any(ranked_prices.attributes_dump), '$'), 'null'), '')) ASC
            """,
        {
            "pb_0": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_1": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_2": "default",
            "pb_3": "",
            "pb_4": 1,
        },
    )


def test_query_with_costs_and_feedback_order() -> None:
    """Test ordering by feedback field with costs enabled.

    This is a regression test to ensure that feedback join fields work correctly
    in the ORDER BY clause when costs are enabled. The OrderField.as_sql method
    should generate the complex expression needed for feedback fields.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("feedback.[wandb.runnable.my_op].payload.output.score", "desc")

    # The key is that feedback ordering requires LEFT JOIN and complex expressions
    # that must be preserved through the cost CTEs
    assert_sql(
        cq,
        """
        WITH filtered_calls AS
            (SELECT calls_merged.id AS id
             FROM calls_merged
             LEFT JOIN (SELECT * FROM feedback WHERE feedback.project_id = {pb_4:String} ) AS feedback ON (feedback.weave_ref = concat('weave-trace-internal:///', {pb_4:String}, '/call/', calls_merged.id))
             PREWHERE calls_merged.project_id = {pb_4:String}
             GROUP BY (calls_merged.project_id,
                       calls_merged.id)
             HAVING (((any(calls_merged.deleted_at) IS NULL))
                     AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
             ORDER BY (NOT (JSONType(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_1:String}, {pb_2:String}) = 'Null'
                            OR JSONType(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_1:String}, {pb_2:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_3:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_3:String}), 'null'), '')) DESC),
             all_calls AS
            (SELECT calls_merged.id AS id,
                    any(calls_merged.started_at) AS started_at
             FROM calls_merged
             LEFT JOIN (SELECT * FROM feedback WHERE feedback.project_id = {pb_4:String} ) AS feedback ON (feedback.weave_ref = concat('weave-trace-internal:///', {pb_4:String}, '/call/', calls_merged.id))
             PREWHERE calls_merged.project_id = {pb_4:String}
             WHERE (calls_merged.id IN filtered_calls)
             GROUP BY (calls_merged.project_id,
                       calls_merged.id)
             ORDER BY (NOT (JSONType(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_1:String}, {pb_2:String}) = 'Null'
                            OR JSONType(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_1:String}, {pb_2:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_3:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_3:String}), 'null'), '')) DESC),
             llm_usage AS
            (-- From the all_calls we get the usage data for LLMs
             SELECT *,
                    ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                    arrayJoin(if(usage_raw != ''
                                 and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\\"requests\\": 0, \\"prompt_tokens\\": 0, \\"completion_tokens\\": 0, \\"total_tokens\\": 0}')])) AS kv,
                    kv.1 AS llm_id,
                    JSONExtractInt(kv.2, 'requests') AS requests,
                    (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0)) AS prompt_tokens,
                    (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0) + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0)) AS completion_tokens,
                    JSONExtractInt(kv.2, 'total_tokens') AS total_tokens
             FROM all_calls),
             ranked_prices AS
            (-- based on the llm_ids in the usage data we get all the prices and rank them according to specificity and effective date
             SELECT *,
                    llm_token_prices.id,
                    llm_token_prices.pricing_level,
                    llm_token_prices.pricing_level_id,
                    llm_token_prices.provider_id,
                    llm_token_prices.llm_id,
                    llm_token_prices.effective_date,
                    llm_token_prices.prompt_token_cost,
                    llm_token_prices.cached_prompt_token_cost,
                    llm_token_prices.completion_token_cost,
                    llm_token_prices.prompt_token_cost_unit,
                    llm_token_prices.cached_prompt_token_cost_unit,
                    llm_token_prices.completion_token_cost_unit,
                    llm_token_prices.created_by,
                    llm_token_prices.created_at,
                    ROW_NUMBER() OVER (PARTITION BY llm_usage.id, llm_usage.llm_id
                                       ORDER BY CASE -- Order by effective_date
                                                    WHEN llm_usage.started_at >= llm_token_prices.effective_date THEN 1
                                                    ELSE 2
                                                END, CASE -- Order by pricing level then by effective_date
                                                     -- WHEN llm_token_prices.pricing_level = 'org' AND llm_token_prices.pricing_level_id = ORG_PARAM THEN 1
                                                         WHEN llm_token_prices.pricing_level = 'project'
                                                              AND llm_token_prices.pricing_level_id = 'UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=' THEN 2
                                                         WHEN llm_token_prices.pricing_level = 'default'
                                                              AND llm_token_prices.pricing_level_id = 'default' THEN 3
                                                         ELSE 4
                                                     END, llm_token_prices.effective_date DESC) AS rank
             FROM llm_usage
             LEFT JOIN llm_token_prices ON ((llm_usage.llm_id = llm_token_prices.llm_id)
                                            AND ((llm_token_prices.pricing_level_id = {pb_5:String})
                                                 OR (llm_token_prices.pricing_level_id = {pb_6:String})
                                                 OR (llm_token_prices.pricing_level_id = {pb_7:String})))) -- Final Select, which just selects the correct fields, and adds a costs object
        SELECT id,
               started_at,
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"cached_prompt_tokens":', toString(least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens)), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',', '"cached_prompt_token_cost":', toString(cached_prompt_token_cost), ',',
                                        '"completion_token_cost":', toString(completion_token_cost), ',', '"prompt_tokens_total_cost":', toString((greatest(prompt_tokens - least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens), 0) * prompt_token_cost) + (least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens) * cached_prompt_token_cost)), ',',
                                        '"cached_prompt_tokens_total_cost":', toString(least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens) * cached_prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit),  '",',
                                        '"cached_prompt_token_cost_unit":"', toString(cached_prompt_token_cost_unit),  '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }'), '}')) AS summary_dump
        FROM ranked_prices
        LEFT JOIN (SELECT * FROM feedback WHERE feedback.project_id = {pb_4:String} ) AS feedback ON (feedback.weave_ref = concat('weave-trace-internal:///', {pb_4:String}, '/call/', ranked_prices.id))
        WHERE (rank = {pb_8:UInt64})
        GROUP BY id,
                 started_at
        ORDER BY (NOT (JSONType(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_1:String}, {pb_2:String}) = 'Null'
                       OR JSONType(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_1:String}, {pb_2:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_3:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_3:String}), 'null'), '')) DESC
        """,
        {
            "pb_0": "wandb.runnable.my_op",
            "pb_1": "output",
            "pb_2": "score",
            "pb_3": '$."output"."score"',
            "pb_4": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_5": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_6": "default",
            "pb_7": "",
            "pb_8": 1,
        },
    )


def test_query_with_costs_and_nested_attributes_order() -> None:
    """Test ordering by nested attributes field (like attributes.sort_key) with costs enabled.

    This is a regression test for the issue where ordering by attributes_dump fields
    would fail when costs were enabled because the field wasn't being added to the
    all_calls CTE, causing "Unknown expression identifier" errors.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("attributes.sort_key", "ASC")

    # The key fix is that attributes_dump must be:
    # 1. Selected in the all_calls CTE (via select_query.select_fields)
    # 2. Available for the complex ORDER BY expression in all CTEs
    # 3. Present in the final GROUP BY and ORDER BY clauses
    assert_sql(
        cq,
        """
            WITH filtered_calls AS
                (SELECT calls_merged.id AS id
                 FROM calls_merged
                 PREWHERE calls_merged.project_id = {pb_2:String}
                 GROUP BY (calls_merged.project_id,
                           calls_merged.id)
                 HAVING (((any(calls_merged.deleted_at) IS NULL))
                         AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
                 ORDER BY (NOT (JSONType(any(calls_merged.attributes_dump), {pb_0:String}) = 'Null'
                                OR JSONType(any(calls_merged.attributes_dump), {pb_0:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')) ASC),
                 all_calls AS
                (SELECT calls_merged.id AS id,
                        any(calls_merged.started_at) AS started_at,
                        any(calls_merged.attributes_dump) AS attributes_dump
                 FROM calls_merged
                 PREWHERE calls_merged.project_id = {pb_2:String}
                 WHERE (calls_merged.id IN filtered_calls)
                 GROUP BY (calls_merged.project_id,
                           calls_merged.id)
                 ORDER BY (NOT (JSONType(any(calls_merged.attributes_dump), {pb_0:String}) = 'Null'
                                OR JSONType(any(calls_merged.attributes_dump), {pb_0:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')) ASC),
             llm_usage AS
            (-- From the all_calls we get the usage data for LLMs
             SELECT *,
                    ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                    arrayJoin(if(usage_raw != ''
                                 and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\\"requests\\": 0, \\"prompt_tokens\\": 0, \\"completion_tokens\\": 0, \\"total_tokens\\": 0}')])) AS kv,
                    kv.1 AS llm_id,
                    JSONExtractInt(kv.2, 'requests') AS requests,
                    (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0)) AS prompt_tokens,
                    (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0) + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0)) AS completion_tokens,
                    JSONExtractInt(kv.2, 'total_tokens') AS total_tokens
             FROM all_calls),
             ranked_prices AS
            (-- based on the llm_ids in the usage data we get all the prices and rank them according to specificity and effective date
             SELECT *,
                    llm_token_prices.id,
                    llm_token_prices.pricing_level,
                    llm_token_prices.pricing_level_id,
                    llm_token_prices.provider_id,
                    llm_token_prices.llm_id,
                    llm_token_prices.effective_date,
                    llm_token_prices.prompt_token_cost,
                    llm_token_prices.cached_prompt_token_cost,
                    llm_token_prices.completion_token_cost,
                    llm_token_prices.prompt_token_cost_unit,
                    llm_token_prices.cached_prompt_token_cost_unit,
                    llm_token_prices.completion_token_cost_unit,
                    llm_token_prices.created_by,
                    llm_token_prices.created_at,
                    ROW_NUMBER() OVER (PARTITION BY llm_usage.id, llm_usage.llm_id
                                       ORDER BY CASE -- Order by effective_date
                                                    WHEN llm_usage.started_at >= llm_token_prices.effective_date THEN 1
                                                    ELSE 2
                                                END, CASE -- Order by pricing level then by effective_date
                                                     -- WHEN llm_token_prices.pricing_level = 'org' AND llm_token_prices.pricing_level_id = ORG_PARAM THEN 1
                                                         WHEN llm_token_prices.pricing_level = 'project'
                                                              AND llm_token_prices.pricing_level_id = 'UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=' THEN 2
                                                         WHEN llm_token_prices.pricing_level = 'default'
                                                              AND llm_token_prices.pricing_level_id = 'default' THEN 3
                                                         ELSE 4
                                                     END, llm_token_prices.effective_date DESC) AS rank
             FROM llm_usage
             LEFT JOIN llm_token_prices ON ((llm_usage.llm_id = llm_token_prices.llm_id)
                                            AND ((llm_token_prices.pricing_level_id = {pb_3:String})
                                                 OR (llm_token_prices.pricing_level_id = {pb_4:String})
                                                 OR (llm_token_prices.pricing_level_id = {pb_5:String})))) -- Final Select, which just selects the correct fields, and adds a costs object
        SELECT id,
               started_at,
               attributes_dump,
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"cached_prompt_tokens":', toString(least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens)), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',', '"cached_prompt_token_cost":', toString(cached_prompt_token_cost), ',',
                                        '"completion_token_cost":', toString(completion_token_cost), ',', '"prompt_tokens_total_cost":', toString((greatest(prompt_tokens - least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens), 0) * prompt_token_cost) + (least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens) * cached_prompt_token_cost)), ',',
                                        '"cached_prompt_tokens_total_cost":', toString(least(greatest((if(JSONHas(kv.2, 'prompt_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'prompt_tokens_details'), 'cached_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens_details'), JSONExtractInt(JSONExtractRaw(kv.2, 'input_tokens_details'), 'cached_tokens'), 0)), 0), prompt_tokens) * cached_prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit),  '",',
                                        '"cached_prompt_token_cost_unit":"', toString(cached_prompt_token_cost_unit),  '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_6:UInt64})
        GROUP BY id,
                 started_at,
                 attributes_dump
        ORDER BY (NOT (JSONType(any(ranked_prices.attributes_dump), {pb_0:String}) = 'Null'
                       OR JSONType(any(ranked_prices.attributes_dump), {pb_0:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(ranked_prices.attributes_dump), {pb_1:String}), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(any(ranked_prices.attributes_dump), {pb_1:String}), 'null'), '')) ASC
        """,
        {
            "pb_0": "sort_key",
            "pb_1": '$."sort_key"',
            "pb_2": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_3": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_4": "default",
            "pb_5": "",
            "pb_6": 1,
        },
    )
