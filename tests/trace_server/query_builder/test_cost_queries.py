"""Tests for calls queries with include_costs=True.

These tests validate that ordering works correctly when costs are included,
which requires using the raw_sql_order_by method in the ORM.
"""

from tests.trace_server.query_builder.utils import assert_sql
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
)


def test_query_light_column_with_costs() -> None:
    """Test basic query with costs (moved from test_calls_query_builder.py)."""
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
                op_names=["test"],
            )
        )
    )
    assert_sql(
        cq,
        r"""
        WITH filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_1:String}
             AND ((calls_merged.op_name IN {pb_0:Array(String)})
                  OR (calls_merged.op_name IS NULL))
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))),
             all_calls AS
          (SELECT calls_merged.id AS id,
                  any(calls_merged.started_at) AS started_at
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_1:String}
             AND (calls_merged.id IN filtered_calls)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\"requests\": 0, \"prompt_tokens\": 0, \"completion_tokens\": 0, \"total_tokens\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens,
                if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens,
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
                llm_token_prices.completion_token_cost,
                llm_token_prices.prompt_token_cost_unit,
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
                                                          AND llm_token_prices.pricing_level_id = 'UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=' THEN 2
                                                     WHEN llm_token_prices.pricing_level = 'default'
                                                          AND llm_token_prices.pricing_level_id = 'default' THEN 3
                                                     ELSE 4
                                                 END, llm_token_prices.effective_date DESC) AS rank
           FROM llm_usage
           LEFT JOIN llm_token_prices ON ((llm_usage.llm_id = llm_token_prices.llm_id)
                                          AND ((llm_token_prices.pricing_level_id = {pb_2:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_3:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_4:String})))) -- Final Select, which just selects the correct fields, and adds a costs object

        SELECT id,
               started_at,
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',', '"prompt_tokens_total_cost":', toString(prompt_tokens * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_5:UInt64})
        GROUP BY id,
                 started_at
        """,
        {
            "pb_0": ["test"],
            "pb_1": "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
            "pb_2": "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
            "pb_3": "default",
            "pb_4": "",
            "pb_5": 1,
        },
    )


def test_query_with_costs_and_dynamic_field_order() -> None:
    """Test that dynamic fields work with costs using raw_sql_order_by.

    This validates the fix for ordering by attributes.sortable_key with costs.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("attributes.sortable_key", "ASC")
    assert_sql(
        cq,
        r"""
        WITH filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_2:String}
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY (NOT (JSONType(any(calls_merged.attributes_dump), {pb_0:String}) = 'Null'
                          OR JSONType(any(calls_merged.attributes_dump), {pb_0:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')) ASC),
             all_calls AS
          (SELECT calls_merged.id AS id,
                  any(calls_merged.started_at) AS started_at
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_2:String}
             AND (calls_merged.id IN filtered_calls)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           ORDER BY (NOT (JSONType(any(calls_merged.attributes_dump), {pb_0:String}) = 'Null'
                          OR JSONType(any(calls_merged.attributes_dump), {pb_0:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')) ASC),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\"requests\": 0, \"prompt_tokens\": 0, \"completion_tokens\": 0, \"total_tokens\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens,
                if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens,
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
                llm_token_prices.completion_token_cost,
                llm_token_prices.prompt_token_cost_unit,
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
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',', '"prompt_tokens_total_cost":', toString(prompt_tokens * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_6:UInt64})
        GROUP BY id,
                 started_at
        ORDER BY (NOT (JSONType(any(ranked_prices.attributes_dump), {pb_0:String}) = 'Null'
                       OR JSONType(any(ranked_prices.attributes_dump), {pb_0:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(ranked_prices.attributes_dump), {pb_1:String}), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(any(ranked_prices.attributes_dump), {pb_1:String}), 'null'), '')) ASC
        """,
        {
            "pb_0": "sortable_key",
            "pb_1": '$."sortable_key"',
            "pb_2": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_3": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_4": "default",
            "pb_5": "",
            "pb_6": 1,
        },
    )


def test_query_with_costs_and_feedback_order() -> None:
    """Test that feedback fields work with costs using raw_sql_order_by.

    This validates the fix for ordering by feedback fields with costs.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("feedback.[wandb.runnable.my_op].payload.score", "DESC")
    assert_sql(
        cq,
        r"""
        WITH filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           LEFT JOIN
             (SELECT *
              FROM feedback
              WHERE feedback.project_id = {pb_3:String} ) AS feedback ON (feedback.weave_ref = concat('weave-trace-internal:///', {pb_3:String}, '/call/', calls_merged.id))
           WHERE calls_merged.project_id = {pb_3:String}
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY (NOT (JSONType(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_1:String}) = 'Null'
                          OR JSONType(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_1:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_2:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_2:String}), 'null'), '')) DESC),
             all_calls AS
          (SELECT calls_merged.id AS id,
                  any(calls_merged.started_at) AS started_at
           FROM calls_merged
           LEFT JOIN
             (SELECT *
              FROM feedback
              WHERE feedback.project_id = {pb_3:String} ) AS feedback ON (feedback.weave_ref = concat('weave-trace-internal:///', {pb_3:String}, '/call/', calls_merged.id))
           WHERE calls_merged.project_id = {pb_3:String}
             AND (calls_merged.id IN filtered_calls)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           ORDER BY (NOT (JSONType(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_1:String}) = 'Null'
                          OR JSONType(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_1:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_2:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_2:String}), 'null'), '')) DESC),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\"requests\": 0, \"prompt_tokens\": 0, \"completion_tokens\": 0, \"total_tokens\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens,
                if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens,
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
                llm_token_prices.completion_token_cost,
                llm_token_prices.prompt_token_cost_unit,
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
                                          AND ((llm_token_prices.pricing_level_id = {pb_4:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_5:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_6:String})))) -- Final Select, which just selects the correct fields, and adds a costs object

        SELECT id,
               started_at,
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',', '"prompt_tokens_total_cost":', toString(prompt_tokens * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_7:UInt64})
        GROUP BY id,
                 started_at
        ORDER BY (NOT (JSONType(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_1:String}) = 'Null'
                       OR JSONType(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_1:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_2:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_0:String}), {pb_2:String}), 'null'), '')) DESC
        """,
        {
            "pb_0": "wandb.runnable.my_op",
            "pb_1": "score",
            "pb_2": '$."score"',
            "pb_3": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_4": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_5": "default",
            "pb_6": "",
            "pb_7": 1,
        },
    )


def test_query_with_costs_and_simple_field_order() -> None:
    """Test that simple fields work with costs.

    This validates that regular fields still work correctly with costs.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("started_at", "DESC")
    assert_sql(
        cq,
        r"""
        WITH filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_0:String}
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY any(calls_merged.started_at) DESC),
             all_calls AS
          (SELECT calls_merged.id AS id,
                  any(calls_merged.started_at) AS started_at
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_0:String}
             AND (calls_merged.id IN filtered_calls)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           ORDER BY any(calls_merged.started_at) DESC),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\"requests\": 0, \"prompt_tokens\": 0, \"completion_tokens\": 0, \"total_tokens\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens,
                if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens,
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
                llm_token_prices.completion_token_cost,
                llm_token_prices.prompt_token_cost_unit,
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
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',', '"prompt_tokens_total_cost":', toString(prompt_tokens * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_4:UInt64})
        GROUP BY id,
                 started_at
        ORDER BY any(ranked_prices.started_at) DESC
        """,
        {
            "pb_0": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_1": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_2": "default",
            "pb_3": "",
            "pb_4": 1,
        },
    )


def test_query_with_costs_and_multiple_orders() -> None:
    """Test multiple ORDER BY fields with costs.

    This validates that multiple order fields work together with costs.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("attributes.priority", "DESC")
    cq.add_order("started_at", "ASC")
    assert_sql(
        cq,
        r"""
        WITH filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_2:String}
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY (NOT (JSONType(any(calls_merged.attributes_dump), {pb_0:String}) = 'Null'
                          OR JSONType(any(calls_merged.attributes_dump), {pb_0:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')) DESC, any(calls_merged.started_at) ASC),
             all_calls AS
          (SELECT calls_merged.id AS id,
                  any(calls_merged.started_at) AS started_at
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_2:String}
             AND (calls_merged.id IN filtered_calls)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           ORDER BY (NOT (JSONType(any(calls_merged.attributes_dump), {pb_0:String}) = 'Null'
                          OR JSONType(any(calls_merged.attributes_dump), {pb_0:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')) DESC, any(calls_merged.started_at) ASC),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\"requests\": 0, \"prompt_tokens\": 0, \"completion_tokens\": 0, \"total_tokens\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens,
                if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens,
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
                llm_token_prices.completion_token_cost,
                llm_token_prices.prompt_token_cost_unit,
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
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',', '"prompt_tokens_total_cost":', toString(prompt_tokens * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_6:UInt64})
        GROUP BY id,
                 started_at
        ORDER BY (NOT (JSONType(any(ranked_prices.attributes_dump), {pb_0:String}) = 'Null'
                       OR JSONType(any(ranked_prices.attributes_dump), {pb_0:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(ranked_prices.attributes_dump), {pb_1:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(any(ranked_prices.attributes_dump), {pb_1:String}), 'null'), '')) DESC, any(ranked_prices.started_at) ASC
        """,
        {
            "pb_0": "priority",
            "pb_1": '$."priority"',
            "pb_2": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_3": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_4": "default",
            "pb_5": "",
            "pb_6": 1,
        },
    )


def test_query_with_costs_and_summary_field_order() -> None:
    """Test that summary fields work with costs.

    This validates ordering by summary.weave.status with costs.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("summary.weave.status", "ASC")
    assert_sql(
        cq,
        r"""
        WITH filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_5:String}
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY CASE
                        WHEN any(calls_merged.exception) IS NOT NULL THEN {pb_1:String}
                        WHEN IFNULL(toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.summary_dump), {pb_0:String}), 'null'), '')), 0) > 0 THEN {pb_4:String}
                        WHEN any(calls_merged.ended_at) IS NULL THEN {pb_2:String}
                        ELSE {pb_3:String}
                    END ASC),
             all_calls AS
          (SELECT calls_merged.id AS id,
                  any(calls_merged.started_at) AS started_at
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_5:String}
             AND (calls_merged.id IN filtered_calls)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           ORDER BY CASE
                        WHEN any(calls_merged.exception) IS NOT NULL THEN {pb_1:String}
                        WHEN IFNULL(toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.summary_dump), {pb_0:String}), 'null'), '')), 0) > 0 THEN {pb_4:String}
                        WHEN any(calls_merged.ended_at) IS NULL THEN {pb_2:String}
                        ELSE {pb_3:String}
                    END ASC),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\"requests\": 0, \"prompt_tokens\": 0, \"completion_tokens\": 0, \"total_tokens\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens,
                if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens,
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
                llm_token_prices.completion_token_cost,
                llm_token_prices.prompt_token_cost_unit,
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
                                          AND ((llm_token_prices.pricing_level_id = {pb_6:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_7:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_8:String})))) -- Final Select, which just selects the correct fields, and adds a costs object

        SELECT id,
               started_at,
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',', '"prompt_tokens_total_cost":', toString(prompt_tokens * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_9:UInt64})
        GROUP BY id,
                 started_at
        ORDER BY CASE
                     WHEN any(ranked_prices.exception) IS NOT NULL THEN {pb_1:String}
                     WHEN IFNULL(toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(ranked_prices.summary_dump), {pb_0:String}), 'null'), '')), 0) > 0 THEN {pb_4:String}
                     WHEN any(ranked_prices.ended_at) IS NULL THEN {pb_2:String}
                     ELSE {pb_3:String}
                 END ASC
        """,
        {
            "pb_0": '$."status_counts"."error"',
            "pb_1": "error",
            "pb_2": "running",
            "pb_3": "success",
            "pb_4": "descendant_error",
            "pb_5": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_6": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_7": "default",
            "pb_8": "",
            "pb_9": 1,
        },
    )


def test_query_with_costs_order_by_id() -> None:
    """Test ordering by id with costs - simplest case.

    This is a sanity check that the most basic ordering still works.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_order("id", "ASC")
    assert_sql(
        cq,
        r"""
        WITH filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_0:String}
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY calls_merged.id ASC),
             all_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_0:String}
             AND (calls_merged.id IN filtered_calls)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           ORDER BY calls_merged.id ASC),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\"requests\": 0, \"prompt_tokens\": 0, \"completion_tokens\": 0, \"total_tokens\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens,
                if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens,
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
                llm_token_prices.completion_token_cost,
                llm_token_prices.prompt_token_cost_unit,
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
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',', '"prompt_tokens_total_cost":', toString(prompt_tokens * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_4:UInt64})
        GROUP BY id
        ORDER BY ranked_prices.id ASC
        """,
        {
            "pb_0": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_1": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_2": "default",
            "pb_3": "",
            "pb_4": 1,
        },
    )


def test_query_with_costs_and_object_ref_order() -> None:
    """Test that object ref fields work with costs using raw_sql_order_by.

    This validates the fix for ordering by object ref fields (with expand_columns) with costs.
    Note: Object refs with costs are complex and may require additional work to fully support.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("inputs.model.temperature", "DESC")
    cq.set_expand_columns(["inputs.model"])
    assert_sql(
        cq,
        r"""
        WITH obj_filter_0 AS
          (SELECT digest,
                  nullIf(coalesce(nullIf(JSON_VALUE(any(val_dump), {pb_1:String}), 'null'), ''), '') AS object_val_dump,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
           GROUP BY project_id,
                    object_id,
                    digest
           UNION ALL SELECT digest,
                            nullIf(coalesce(nullIf(JSON_VALUE(any(val_dump), {pb_1:String}), 'null'), ''), '') AS object_val_dump,
                            digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
           GROUP BY project_id,
                    digest),
             filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           LEFT JOIN obj_filter_0 ON (coalesce(nullIf(JSON_VALUE(calls_merged.inputs_dump, {pb_2:String}), 'null'), '') = obj_filter_0.ref
                                      OR regexpExtract(coalesce(nullIf(JSON_VALUE(calls_merged.inputs_dump, {pb_2:String}), 'null'), ''), '/([^/]+)$', 1) = obj_filter_0.ref)
           WHERE calls_merged.project_id = {pb_0:String}
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY (NOT (JSONType(any(obj_filter_0.object_val_dump)) = 'Null'
                          OR JSONType(any(obj_filter_0.object_val_dump)) IS NULL)) desc, toFloat64OrNull(any(obj_filter_0.object_val_dump)) DESC, toString(any(obj_filter_0.object_val_dump)) DESC),
             all_calls AS
          (SELECT calls_merged.id AS id,
                  any(calls_merged.started_at) AS started_at
           FROM calls_merged
           LEFT JOIN obj_filter_0 ON (coalesce(nullIf(JSON_VALUE(calls_merged.inputs_dump, {pb_2:String}), 'null'), '') = obj_filter_0.ref
                                      OR regexpExtract(coalesce(nullIf(JSON_VALUE(calls_merged.inputs_dump, {pb_2:String}), 'null'), ''), '/([^/]+)$', 1) = obj_filter_0.ref)
           WHERE calls_merged.project_id = {pb_0:String}
             AND (calls_merged.id IN filtered_calls)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           ORDER BY (NOT (JSONType(any(obj_filter_0.object_val_dump)) = 'Null'
                          OR JSONType(any(obj_filter_0.object_val_dump)) IS NULL)) desc, toFloat64OrNull(any(obj_filter_0.object_val_dump)) DESC, toString(any(obj_filter_0.object_val_dump)) DESC),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\"requests\": 0, \"prompt_tokens\": 0, \"completion_tokens\": 0, \"total_tokens\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens,
                if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens,
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
                llm_token_prices.completion_token_cost,
                llm_token_prices.prompt_token_cost_unit,
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
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',', '"prompt_tokens_total_cost":', toString(prompt_tokens * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_9:UInt64})
        GROUP BY id,
                 started_at
        ORDER BY (NOT (JSONType(any(ranked_prices.inputs_dump), {pb_6:String}, {pb_7:String}) = 'Null'
                       OR JSONType(any(ranked_prices.inputs_dump), {pb_6:String}, {pb_7:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(ranked_prices.inputs_dump), {pb_8:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(any(ranked_prices.inputs_dump), {pb_8:String}), 'null'), '')) DESC
        """,
        {
            "pb_0": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_1": '$."temperature"',
            "pb_2": '$."model"',
            "pb_3": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_4": "default",
            "pb_5": "",
            "pb_6": "model",
            "pb_7": "temperature",
            "pb_8": '$."model"."temperature"',
            "pb_9": 1,
        },
    )


def test_query_with_costs_order_desc() -> None:
    """Test DESC ordering with costs."""
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("started_at", "DESC")
    assert_sql(
        cq,
        r"""
        WITH filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_0:String}
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY any(calls_merged.started_at) DESC),
             all_calls AS
          (SELECT calls_merged.id AS id,
                  any(calls_merged.started_at) AS started_at
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_0:String}
             AND (calls_merged.id IN filtered_calls)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           ORDER BY any(calls_merged.started_at) DESC),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\"requests\": 0, \"prompt_tokens\": 0, \"completion_tokens\": 0, \"total_tokens\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens,
                if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens,
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
                llm_token_prices.completion_token_cost,
                llm_token_prices.prompt_token_cost_unit,
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
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',', '"prompt_tokens_total_cost":', toString(prompt_tokens * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_4:UInt64})
        GROUP BY id,
                 started_at
        ORDER BY any(ranked_prices.started_at) DESC
        """,
        {
            "pb_0": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_1": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_2": "default",
            "pb_3": "",
            "pb_4": 1,
        },
    )


def test_query_with_costs_order_asc() -> None:
    """Test ASC ordering with costs."""
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("started_at")
    cq.add_order("started_at", "ASC")
    assert_sql(
        cq,
        r"""
        WITH filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_0:String}
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY any(calls_merged.started_at) ASC),
             all_calls AS
          (SELECT calls_merged.id AS id,
                  any(calls_merged.started_at) AS started_at
           FROM calls_merged
           WHERE calls_merged.project_id = {pb_0:String}
             AND (calls_merged.id IN filtered_calls)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           ORDER BY any(calls_merged.started_at) ASC),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\"requests\": 0, \"prompt_tokens\": 0, \"completion_tokens\": 0, \"total_tokens\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'input_tokens')) AS prompt_tokens,
                if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'output_tokens')) AS completion_tokens,
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
                llm_token_prices.completion_token_cost,
                llm_token_prices.prompt_token_cost_unit,
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
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',', '"prompt_tokens_total_cost":', toString(prompt_tokens * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_4:UInt64})
        GROUP BY id,
                 started_at
        ORDER BY any(ranked_prices.started_at) ASC
        """,
        {
            "pb_0": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_1": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
            "pb_2": "default",
            "pb_3": "",
            "pb_4": 1,
        },
    )
