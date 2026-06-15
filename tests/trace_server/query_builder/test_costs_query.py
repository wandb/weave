import pytest

from tests.trace_server.query_builder.utils import assert_sql
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
)
from weave.trace_server.ch_sentinel_values import SENTINEL_EPOCH
from weave.trace_server.project_version.types import ReadTable

PROJECT_MERGED = "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc="
PROJECT_COMPLETE = "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc="


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
                AND ((NOT ((any(calls_merged.op_name) IS NULL))))
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
                            [('weave_dummy_llm_id', '{\\"requests\\": 0, \\"prompt_tokens\\": 0, \\"completion_tokens\\": 0, \\"total_tokens\\": 0, \\"cache_read_input_tokens\\": 0, \\"cache_creation_input_tokens\\": 0}')]
                        )
                    ) AS kv,
                    kv.1 AS llm_id,
                    JSONExtractInt(kv.2, 'requests') AS requests,
                    (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0)) AS prompt_tokens,
                    (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0) + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0)) AS completion_tokens,
                    JSONExtractInt(kv.2, 'total_tokens') AS total_tokens,
                    JSONExtractInt(kv.2, 'cache_read_input_tokens') AS cache_read_input_tokens,
                    JSONExtractInt(kv.2, 'cache_creation_input_tokens') AS cache_creation_input_tokens
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
                    llm_token_prices.completion_token_cost,
                    llm_token_prices.cache_read_input_token_cost,
                    llm_token_prices.cache_creation_input_token_cost,
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
                                        '"cache_read_input_tokens":', toString(cache_read_input_tokens), ',',
                                        '"cache_creation_input_tokens":', toString(cache_creation_input_tokens), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',',
                                        '"completion_token_cost":', toString(completion_token_cost), ',',
                                        '"cache_read_input_token_cost":', toString(cache_read_input_token_cost), ',',
                                        '"cache_creation_input_token_cost":', toString(cache_creation_input_token_cost), ',',
                                        '"prompt_tokens_total_cost":', toString((prompt_tokens - cache_read_input_tokens - cache_creation_input_tokens) * prompt_token_cost), ',',
                                        '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',',
                                        '"cache_read_input_tokens_total_cost":', toString(cache_read_input_tokens * cache_read_input_token_cost), ',',
                                        '"cache_creation_input_tokens_total_cost":', toString(cache_creation_input_tokens * cache_creation_input_token_cost), ',',
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


# Each param keeps its OWN complete expected SQL + params: the cost CTE bodies
# diverge by ORDER BY shape, JSON path, GROUP BY membership, and the feedback
# LEFT JOIN per CTE, so no string is folded away.
@pytest.mark.parametrize(
    ("orders", "expected_sql", "expected_params"),
    [
        # Test ordering by attributes_dump and summary.weave.status fields when costs are enabled.
        pytest.param(
            [("attributes_dump", "ASC"), ("summary.weave.status", "ASC")],
            """WITH filtered_calls AS
  (SELECT calls_merged.id AS id
   FROM calls_merged PREWHERE calls_merged.project_id = {pb_5:String}
   GROUP BY (calls_merged.project_id,
             calls_merged.id)
   HAVING (((any(calls_merged.deleted_at) IS NULL))
           AND ((NOT ((any(calls_merged.op_name) IS NULL)))))
   ORDER BY (NOT (JSONType(any(calls_merged.attributes_dump)) = 'Null'
                  OR JSONType(any(calls_merged.attributes_dump)) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), '$'), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), '$'), 'null'), '')) ASC, CASE
                                                                                                                                                                                                                                                                                            WHEN any(calls_merged.exception) IS NOT NULL THEN {pb_1:String}
                                                                                                                                                                                                                                                                                            WHEN IFNULL(toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.summary_dump), {pb_0:String}), 'null'), '')), 0) > 0 THEN {pb_4:String}
                                                                                                                                                                                                                                                                                            WHEN any(calls_merged.ended_at) IS NULL THEN {pb_2:String}
                                                                                                                                                                                                                                                                                            ELSE {pb_3:String}
                                                                                                                                                                                                                                                                                        END ASC),
     all_calls AS
  (SELECT calls_merged.id AS id,
          any(calls_merged.started_at) AS started_at,
          any(calls_merged.attributes_dump) AS attributes_dump,
          CASE
              WHEN any(calls_merged.exception) IS NOT NULL THEN {pb_1:String}
              WHEN IFNULL(toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.summary_dump), {pb_0:String}), 'null'), '')), 0) > 0 THEN {pb_4:String}
              WHEN any(calls_merged.ended_at) IS NULL THEN {pb_2:String}
              ELSE {pb_3:String}
          END AS `summary.weave.status`
   FROM calls_merged PREWHERE calls_merged.project_id = {pb_5:String}
   WHERE (calls_merged.id IN filtered_calls)
   GROUP BY (calls_merged.project_id,
             calls_merged.id)
   ORDER BY (NOT (JSONType(any(calls_merged.attributes_dump)) = 'Null'
                  OR JSONType(any(calls_merged.attributes_dump)) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), '$'), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), '$'), 'null'), '')) ASC, CASE
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
                     and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\\"requests\\": 0, \\"prompt_tokens\\": 0, \\"completion_tokens\\": 0, \\"total_tokens\\": 0, \\"cache_read_input_tokens\\": 0, \\"cache_creation_input_tokens\\": 0}')])) AS kv,
        kv.1 AS llm_id,
        JSONExtractInt(kv.2, 'requests') AS requests,
        (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0)) AS prompt_tokens,
        (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0) + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0)) AS completion_tokens,
        JSONExtractInt(kv.2, 'total_tokens') AS total_tokens,
        JSONExtractInt(kv.2, 'cache_read_input_tokens') AS cache_read_input_tokens,
        JSONExtractInt(kv.2, 'cache_creation_input_tokens') AS cache_creation_input_tokens
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
        llm_token_prices.cache_read_input_token_cost,
        llm_token_prices.cache_creation_input_token_cost,
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
       attributes_dump,
       `summary.weave.status`,
       if(any(llm_id) = 'weave_dummy_llm_id'
          or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',',
                                        '"cache_read_input_tokens":', toString(cache_read_input_tokens), ',',
                                        '"cache_creation_input_tokens":', toString(cache_creation_input_tokens), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',',
                                        '"cache_read_input_token_cost":', toString(cache_read_input_token_cost), ',',
                                        '"cache_creation_input_token_cost":', toString(cache_creation_input_token_cost), ',',
                                        '"prompt_tokens_total_cost":', toString((prompt_tokens - cache_read_input_tokens - cache_creation_input_tokens) * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',',
                                        '"cache_read_input_tokens_total_cost":', toString(cache_read_input_tokens * cache_read_input_token_cost), ',',
                                        '"cache_creation_input_tokens_total_cost":', toString(cache_creation_input_tokens * cache_creation_input_token_cost), ',',
                                        '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }'), '}')) AS summary_dump
FROM ranked_prices
WHERE (rank = {pb_9:UInt64})
GROUP BY id,
         started_at,
         attributes_dump,
         `summary.weave.status`
ORDER BY (NOT (JSONType(ranked_prices.attributes_dump) = 'Null'
               OR JSONType(ranked_prices.attributes_dump) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(ranked_prices.attributes_dump, '$'), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(ranked_prices.attributes_dump, '$'), 'null'), '')) ASC, `summary.weave.status` ASC""",
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
            id="test_query_with_costs_and_attributes_order",
        ),
        # Test ordering by a user-defined summary field when costs are enabled.
        pytest.param(
            [("summary.acuracia", "DESC")],
            """WITH filtered_calls AS
  (SELECT calls_merged.id AS id
   FROM calls_merged PREWHERE calls_merged.project_id = {pb_2:String}
   GROUP BY (calls_merged.project_id,
             calls_merged.id)
   HAVING (((any(calls_merged.deleted_at) IS NULL))
           AND ((NOT ((any(calls_merged.op_name) IS NULL)))))
   ORDER BY (NOT (JSONType(any(calls_merged.summary_dump), {pb_0:String}) = 'Null'
                  OR JSONType(any(calls_merged.summary_dump), {pb_0:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.summary_dump), {pb_1:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(any(calls_merged.summary_dump), {pb_1:String}), 'null'), '')) DESC),
     all_calls AS
  (SELECT calls_merged.id AS id,
          any(calls_merged.started_at) AS started_at,
          any(calls_merged.summary_dump) AS summary_dump
   FROM calls_merged PREWHERE calls_merged.project_id = {pb_2:String}
   WHERE (calls_merged.id IN filtered_calls)
   GROUP BY (calls_merged.project_id,
             calls_merged.id)
   ORDER BY (NOT (JSONType(any(calls_merged.summary_dump), {pb_0:String}) = 'Null'
                  OR JSONType(any(calls_merged.summary_dump), {pb_0:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.summary_dump), {pb_1:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(any(calls_merged.summary_dump), {pb_1:String}), 'null'), '')) DESC),
     llm_usage AS
  (-- From the all_calls we get the usage data for LLMs
 SELECT *,
        ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
        arrayJoin(if(usage_raw != ''
                     and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\\"requests\\": 0, \\"prompt_tokens\\": 0, \\"completion_tokens\\": 0, \\"total_tokens\\": 0, \\"cache_read_input_tokens\\": 0, \\"cache_creation_input_tokens\\": 0}')])) AS kv,
        kv.1 AS llm_id,
        JSONExtractInt(kv.2, 'requests') AS requests,
        (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0)) AS prompt_tokens,
        (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0) + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0)) AS completion_tokens,
        JSONExtractInt(kv.2, 'total_tokens') AS total_tokens,
        JSONExtractInt(kv.2, 'cache_read_input_tokens') AS cache_read_input_tokens,
        JSONExtractInt(kv.2, 'cache_creation_input_tokens') AS cache_creation_input_tokens
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
        llm_token_prices.cache_read_input_token_cost,
        llm_token_prices.cache_creation_input_token_cost,
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
          or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',',
                                        '"cache_read_input_tokens":', toString(cache_read_input_tokens), ',',
                                        '"cache_creation_input_tokens":', toString(cache_creation_input_tokens), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',',
                                        '"cache_read_input_token_cost":', toString(cache_read_input_token_cost), ',',
                                        '"cache_creation_input_token_cost":', toString(cache_creation_input_token_cost), ',',
                                        '"prompt_tokens_total_cost":', toString((prompt_tokens - cache_read_input_tokens - cache_creation_input_tokens) * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',',
                                        '"cache_read_input_tokens_total_cost":', toString(cache_read_input_tokens * cache_read_input_token_cost), ',',
                                        '"cache_creation_input_tokens_total_cost":', toString(cache_creation_input_tokens * cache_creation_input_token_cost), ',',
                                        '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }'), '}')) AS summary_dump
FROM ranked_prices
WHERE (rank = {pb_6:UInt64})
GROUP BY id,
         started_at
ORDER BY (NOT (JSONType(any(ranked_prices.summary_dump), {pb_0:String}) = 'Null'
               OR JSONType(any(ranked_prices.summary_dump), {pb_0:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(ranked_prices.summary_dump), {pb_1:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(any(ranked_prices.summary_dump), {pb_1:String}), 'null'), '')) DESC""",
            {
                "pb_0": "acuracia",
                "pb_1": '$."acuracia"',
                "pb_2": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
                "pb_3": "UHJvamVjdEludGVybmFsSWQ6NDI3Mjk1MTc=",
                "pb_4": "default",
                "pb_5": "",
                "pb_6": 1,
            },
            id="test_query_with_costs_and_dynamic_summary_order",
        ),
        # Test ordering by feedback field with costs enabled.
        pytest.param(
            [("feedback.[wandb.runnable.my_op].payload.output.score", "desc")],
            """
        WITH filtered_calls AS
            (SELECT calls_merged.id AS id
             FROM calls_merged
             LEFT JOIN (SELECT * FROM feedback WHERE feedback.project_id = {pb_4:String} ) AS feedback ON (feedback.weave_ref = concat('weave-trace-internal:///', {pb_4:String}, '/call/', calls_merged.id))
             PREWHERE calls_merged.project_id = {pb_4:String}
             GROUP BY (calls_merged.project_id,
                       calls_merged.id)
             HAVING (((any(calls_merged.deleted_at) IS NULL))
                     AND ((NOT ((any(calls_merged.op_name) IS NULL)))))
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
                                 and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\\"requests\\": 0, \\"prompt_tokens\\": 0, \\"completion_tokens\\": 0, \\"total_tokens\\": 0, \\"cache_read_input_tokens\\": 0, \\"cache_creation_input_tokens\\": 0}')])) AS kv,
                    kv.1 AS llm_id,
                    JSONExtractInt(kv.2, 'requests') AS requests,
                    (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0)) AS prompt_tokens,
                    (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0) + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0)) AS completion_tokens,
                    JSONExtractInt(kv.2, 'total_tokens') AS total_tokens,
                    JSONExtractInt(kv.2, 'cache_read_input_tokens') AS cache_read_input_tokens,
                    JSONExtractInt(kv.2, 'cache_creation_input_tokens') AS cache_creation_input_tokens
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
                    llm_token_prices.cache_read_input_token_cost,
                    llm_token_prices.cache_creation_input_token_cost,
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
                                            AND ((llm_token_prices.pricing_level_id = {pb_5:String})
                                                 OR (llm_token_prices.pricing_level_id = {pb_6:String})
                                                 OR (llm_token_prices.pricing_level_id = {pb_7:String})))) -- Final Select, which just selects the correct fields, and adds a costs object
        SELECT id,
               started_at,
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',',
                                        '"cache_read_input_tokens":', toString(cache_read_input_tokens), ',',
                                        '"cache_creation_input_tokens":', toString(cache_creation_input_tokens), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',',
                                        '"cache_read_input_token_cost":', toString(cache_read_input_token_cost), ',',
                                        '"cache_creation_input_token_cost":', toString(cache_creation_input_token_cost), ',',
                                        '"prompt_tokens_total_cost":', toString((prompt_tokens - cache_read_input_tokens - cache_creation_input_tokens) * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',',
                                        '"cache_read_input_tokens_total_cost":', toString(cache_read_input_tokens * cache_read_input_token_cost), ',',
                                        '"cache_creation_input_tokens_total_cost":', toString(cache_creation_input_tokens * cache_creation_input_token_cost), ',',
                                        '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }'), '}')) AS summary_dump
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
            id="test_query_with_costs_and_feedback_order",
        ),
        # Test ordering by nested attributes field (like attributes.sort_key) with costs enabled.
        pytest.param(
            [("attributes.sort_key", "ASC")],
            """
            WITH filtered_calls AS
                (SELECT calls_merged.id AS id
                 FROM calls_merged
                 PREWHERE calls_merged.project_id = {pb_2:String}
                 GROUP BY (calls_merged.project_id,
                           calls_merged.id)
                 HAVING (((any(calls_merged.deleted_at) IS NULL))
                         AND ((NOT ((any(calls_merged.op_name) IS NULL)))))
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
                                 and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\\"requests\\": 0, \\"prompt_tokens\\": 0, \\"completion_tokens\\": 0, \\"total_tokens\\": 0, \\"cache_read_input_tokens\\": 0, \\"cache_creation_input_tokens\\": 0}')])) AS kv,
                    kv.1 AS llm_id,
                    JSONExtractInt(kv.2, 'requests') AS requests,
                    (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0)) AS prompt_tokens,
                    (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0) + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0)) AS completion_tokens,
                    JSONExtractInt(kv.2, 'total_tokens') AS total_tokens,
                    JSONExtractInt(kv.2, 'cache_read_input_tokens') AS cache_read_input_tokens,
                    JSONExtractInt(kv.2, 'cache_creation_input_tokens') AS cache_creation_input_tokens
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
                    llm_token_prices.cache_read_input_token_cost,
                    llm_token_prices.cache_creation_input_token_cost,
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
               attributes_dump,
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',',
                                        '"cache_read_input_tokens":', toString(cache_read_input_tokens), ',',
                                        '"cache_creation_input_tokens":', toString(cache_creation_input_tokens), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',',
                                        '"cache_read_input_token_cost":', toString(cache_read_input_token_cost), ',',
                                        '"cache_creation_input_token_cost":', toString(cache_creation_input_token_cost), ',',
                                        '"prompt_tokens_total_cost":', toString((prompt_tokens - cache_read_input_tokens - cache_creation_input_tokens) * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',',
                                        '"cache_read_input_tokens_total_cost":', toString(cache_read_input_tokens * cache_read_input_token_cost), ',',
                                        '"cache_creation_input_tokens_total_cost":', toString(cache_creation_input_tokens * cache_creation_input_token_cost), ',',
                                        '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_6:UInt64})
        GROUP BY id,
                 started_at,
                 attributes_dump
        ORDER BY (NOT (JSONType(ranked_prices.attributes_dump, {pb_0:String}) = 'Null'
                       OR JSONType(ranked_prices.attributes_dump, {pb_0:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(ranked_prices.attributes_dump, {pb_1:String}), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(ranked_prices.attributes_dump, {pb_1:String}), 'null'), '')) ASC
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
            id="test_query_with_costs_and_nested_attributes_order",
        ),
    ],
)
def test_query_with_costs_calls_merged_order(
    orders: list[tuple[str, str]], expected_sql: str, expected_params: dict
) -> None:
    cq = CallsQuery(project_id=PROJECT_MERGED, include_costs=True)
    cq.add_field("id")
    cq.add_field("started_at")
    for field, direction in orders:
        cq.add_order(field, direction)
    assert_sql(cq, expected_sql, expected_params)


def test_query_calls_complete_with_costs_light_fields() -> None:
    """Test calls_complete with costs uses a single all_calls CTE instead of filtered_calls + all_calls.

    For calls_complete, there is no GROUP BY / aggregation needed, so the optimizer
    skips the two-step filtered_calls CTE and wraps the base query directly as all_calls.
    The all_calls CTE feeds into the standard llm_usage -> ranked_prices cost pipeline.
    """
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
        include_costs=True,
        read_table=ReadTable.CALLS_COMPLETE,
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
        WITH all_calls AS
          (SELECT calls_complete.id AS id,
                  calls_complete.started_at AS started_at
           FROM calls_complete PREWHERE calls_complete.project_id = {pb_2:String}
           WHERE ((calls_complete.op_name IN {pb_1:Array(String)})
                  OR (calls_complete.op_name IS NULL))
             AND (calls_complete.deleted_at = {pb_0:DateTime64(3)})),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\\"requests\\": 0, \\"prompt_tokens\\": 0, \\"completion_tokens\\": 0, \\"total_tokens\\": 0, \\"cache_read_input_tokens\\": 0, \\"cache_creation_input_tokens\\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0)) AS prompt_tokens,
                (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0) + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0)) AS completion_tokens,
                JSONExtractInt(kv.2, 'total_tokens') AS total_tokens,
                JSONExtractInt(kv.2, 'cache_read_input_tokens') AS cache_read_input_tokens,
                JSONExtractInt(kv.2, 'cache_creation_input_tokens') AS cache_creation_input_tokens
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
                llm_token_prices.cache_read_input_token_cost,
                llm_token_prices.cache_creation_input_token_cost,
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
                                          AND ((llm_token_prices.pricing_level_id = {pb_3:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_4:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_5:String})))) -- Final Select, which just selects the correct fields, and adds a costs object
        SELECT id,
               started_at,
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',',
                                        '"cache_read_input_tokens":', toString(cache_read_input_tokens), ',',
                                        '"cache_creation_input_tokens":', toString(cache_creation_input_tokens), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',',
                                        '"cache_read_input_token_cost":', toString(cache_read_input_token_cost), ',',
                                        '"cache_creation_input_token_cost":', toString(cache_creation_input_token_cost), ',',
                                        '"prompt_tokens_total_cost":', toString((prompt_tokens - cache_read_input_tokens - cache_creation_input_tokens) * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',',
                                        '"cache_read_input_tokens_total_cost":', toString(cache_read_input_tokens * cache_read_input_token_cost), ',',
                                        '"cache_creation_input_tokens_total_cost":', toString(cache_creation_input_tokens * cache_creation_input_token_cost), ',',
                                        '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }'), '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_6:UInt64})
        GROUP BY id,
                 started_at
        """,
        {
            "pb_0": SENTINEL_EPOCH,
            "pb_1": ["a", "b"],
            "pb_2": "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
            "pb_3": "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
            "pb_4": "default",
            "pb_5": "",
            "pb_6": 1,
        },
    )


# calls_complete skips the filtered_calls CTE entirely (direct columns / SELECT
# DISTINCT / CASE-WHEN trace_name). Each param retains its full expected SQL.
@pytest.mark.parametrize(
    ("orders", "expected_sql", "expected_params"),
    [
        # Test calls_complete with costs and heavy field ordering skips filtered_calls CTE.
        pytest.param(
            [("attributes.sort_key", "ASC")],
            """
        WITH all_calls AS
          (SELECT calls_complete.id AS id,
                  calls_complete.started_at AS started_at,
                  calls_complete.attributes_dump AS attributes_dump
           FROM calls_complete PREWHERE calls_complete.project_id = {pb_3:String}
           WHERE 1
             AND (calls_complete.deleted_at = {pb_0:DateTime64(3)})
           ORDER BY (NOT (JSONType(calls_complete.attributes_dump, {pb_1:String}) = 'Null'
                          OR JSONType(calls_complete.attributes_dump, {pb_1:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(calls_complete.attributes_dump, {pb_2:String}), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(calls_complete.attributes_dump, {pb_2:String}), 'null'), '')) ASC),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\\"requests\\": 0, \\"prompt_tokens\\": 0, \\"completion_tokens\\": 0, \\"total_tokens\\": 0, \\"cache_read_input_tokens\\": 0, \\"cache_creation_input_tokens\\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0)) AS prompt_tokens,
                (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0) + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0)) AS completion_tokens,
                JSONExtractInt(kv.2, 'total_tokens') AS total_tokens,
                JSONExtractInt(kv.2, 'cache_read_input_tokens') AS cache_read_input_tokens,
                JSONExtractInt(kv.2, 'cache_creation_input_tokens') AS cache_creation_input_tokens
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
                llm_token_prices.cache_read_input_token_cost,
                llm_token_prices.cache_creation_input_token_cost,
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
                                          AND ((llm_token_prices.pricing_level_id = {pb_4:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_5:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_6:String})))) -- Final Select, which just selects the correct fields, and adds a costs object
        SELECT id,
               started_at,
               attributes_dump,
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',',
                                        '"cache_read_input_tokens":', toString(cache_read_input_tokens), ',',
                                        '"cache_creation_input_tokens":', toString(cache_creation_input_tokens), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',',
                                        '"cache_read_input_token_cost":', toString(cache_read_input_token_cost), ',',
                                        '"cache_creation_input_token_cost":', toString(cache_creation_input_token_cost), ',',
                                        '"prompt_tokens_total_cost":', toString((prompt_tokens - cache_read_input_tokens - cache_creation_input_tokens) * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',',
                                        '"cache_read_input_tokens_total_cost":', toString(cache_read_input_tokens * cache_read_input_token_cost), ',',
                                        '"cache_creation_input_tokens_total_cost":', toString(cache_creation_input_tokens * cache_creation_input_token_cost), ',',
                                        '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_7:UInt64})
        GROUP BY id,
                 started_at,
                 attributes_dump
        ORDER BY (NOT (JSONType(ranked_prices.attributes_dump, {pb_1:String}) = 'Null'
                       OR JSONType(ranked_prices.attributes_dump, {pb_1:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(ranked_prices.attributes_dump, {pb_2:String}), 'null'), '')) ASC, toString(coalesce(nullIf(JSON_VALUE(ranked_prices.attributes_dump, {pb_2:String}), 'null'), '')) ASC
        """,
            {
                "pb_0": SENTINEL_EPOCH,
                "pb_1": "sort_key",
                "pb_2": '$."sort_key"',
                "pb_3": "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
                "pb_4": "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
                "pb_5": "default",
                "pb_6": "",
                "pb_7": 1,
            },
            id="test_query_calls_complete_with_costs_and_attributes_order",
        ),
        # Test calls_complete with costs and feedback ordering skips filtered_calls CTE.
        pytest.param(
            [("feedback.[wandb.runnable.my_op].payload.output.score", "desc")],
            """
        WITH all_calls AS
          (SELECT DISTINCT calls_complete.id AS id,
                  calls_complete.started_at AS started_at
           FROM calls_complete
           LEFT JOIN
             (SELECT *
              FROM feedback
              WHERE feedback.project_id = {pb_5:String} ) AS feedback ON (feedback.weave_ref = concat('weave-trace-internal:///', {pb_5:String}, '/call/', calls_complete.id)) PREWHERE calls_complete.project_id = {pb_5:String}
           WHERE 1
             AND (calls_complete.deleted_at = {pb_0:DateTime64(3)})
           ORDER BY (NOT (JSONType(CASE
                                       WHEN feedback.feedback_type = {pb_1:String} THEN feedback.payload_dump
                                   END, {pb_2:String}, {pb_3:String}) = 'Null'
                          OR JSONType(CASE
                                          WHEN feedback.feedback_type = {pb_1:String} THEN feedback.payload_dump
                                      END, {pb_2:String}, {pb_3:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(CASE
                                                                                                                                        WHEN feedback.feedback_type = {pb_1:String} THEN feedback.payload_dump
                                                                                                                                    END, {pb_4:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(CASE
                                                                                                                                                                                                                     WHEN feedback.feedback_type = {pb_1:String} THEN feedback.payload_dump
                                                                                                                                                                                                                 END, {pb_4:String}), 'null'), '')) DESC),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\\"requests\\": 0, \\"prompt_tokens\\": 0, \\"completion_tokens\\": 0, \\"total_tokens\\": 0, \\"cache_read_input_tokens\\": 0, \\"cache_creation_input_tokens\\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0)) AS prompt_tokens,
                (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0) + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0)) AS completion_tokens,
                JSONExtractInt(kv.2, 'total_tokens') AS total_tokens,
                JSONExtractInt(kv.2, 'cache_read_input_tokens') AS cache_read_input_tokens,
                JSONExtractInt(kv.2, 'cache_creation_input_tokens') AS cache_creation_input_tokens
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
                llm_token_prices.cache_read_input_token_cost,
                llm_token_prices.cache_creation_input_token_cost,
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
                                          AND ((llm_token_prices.pricing_level_id = {pb_6:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_7:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_8:String})))) -- Final Select, which just selects the correct fields, and adds a costs object
        SELECT id,
               started_at,
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',',
                                        '"cache_read_input_tokens":', toString(cache_read_input_tokens), ',',
                                        '"cache_creation_input_tokens":', toString(cache_creation_input_tokens), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',',
                                        '"cache_read_input_token_cost":', toString(cache_read_input_token_cost), ',',
                                        '"cache_creation_input_token_cost":', toString(cache_creation_input_token_cost), ',',
                                        '"prompt_tokens_total_cost":', toString((prompt_tokens - cache_read_input_tokens - cache_creation_input_tokens) * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',',
                                        '"cache_read_input_tokens_total_cost":', toString(cache_read_input_tokens * cache_read_input_token_cost), ',',
                                        '"cache_creation_input_tokens_total_cost":', toString(cache_creation_input_tokens * cache_creation_input_token_cost), ',',
                                        '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }'), '}')) AS summary_dump
        FROM ranked_prices
        LEFT JOIN (SELECT * FROM feedback WHERE feedback.project_id = {pb_5:String} ) AS feedback ON (feedback.weave_ref = concat('weave-trace-internal:///', {pb_5:String}, '/call/', ranked_prices.id))
        WHERE (rank = {pb_9:UInt64})
        GROUP BY id,
                 started_at
        ORDER BY (NOT (JSONType(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_1:String}), {pb_2:String}, {pb_3:String}) = 'Null'
                       OR JSONType(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_1:String}), {pb_2:String}, {pb_3:String}) IS NULL)) desc, toFloat64OrNull(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_1:String}), {pb_4:String}), 'null'), '')) DESC, toString(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump, feedback.feedback_type = {pb_1:String}), {pb_4:String}), 'null'), '')) DESC
        """,
            {
                "pb_0": SENTINEL_EPOCH,
                "pb_1": "wandb.runnable.my_op",
                "pb_2": "output",
                "pb_3": "score",
                "pb_4": '$."output"."score"',
                "pb_5": "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
                "pb_6": "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
                "pb_7": "default",
                "pb_8": "",
                "pb_9": 1,
            },
            id="test_query_calls_complete_with_costs_and_feedback_order",
        ),
        # Test calls_complete with costs and summary.weave.trace_name ordering.
        pytest.param(
            [("summary.weave.trace_name", "DESC")],
            """
        WITH all_calls AS
          (SELECT calls_complete.id AS id,
                  calls_complete.started_at AS started_at,
                  CASE
                      WHEN calls_complete.display_name != {pb_0:String} THEN calls_complete.display_name
                      WHEN calls_complete.op_name IS NOT NULL
                           AND calls_complete.op_name LIKE 'weave-trace-internal:///%' THEN regexpExtract(toString(calls_complete.op_name), '/([^/:]*):', 1)
                      ELSE calls_complete.op_name
                  END AS `summary.weave.trace_name`
           FROM calls_complete PREWHERE calls_complete.project_id = {pb_3:String}
           WHERE 1
             AND (calls_complete.deleted_at = {pb_1:DateTime64(3)})
           ORDER BY CASE
                        WHEN calls_complete.display_name != {pb_2:String} THEN calls_complete.display_name
                        WHEN calls_complete.op_name IS NOT NULL
                             AND calls_complete.op_name LIKE 'weave-trace-internal:///%' THEN regexpExtract(toString(calls_complete.op_name), '/([^/:]*):', 1)
                        ELSE calls_complete.op_name
                    END DESC),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\\"requests\\": 0, \\"prompt_tokens\\": 0, \\"completion_tokens\\": 0, \\"total_tokens\\": 0, \\"cache_read_input_tokens\\": 0, \\"cache_creation_input_tokens\\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0)) AS prompt_tokens,
                (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0) + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0)) AS completion_tokens,
                JSONExtractInt(kv.2, 'total_tokens') AS total_tokens,
                JSONExtractInt(kv.2, 'cache_read_input_tokens') AS cache_read_input_tokens,
                JSONExtractInt(kv.2, 'cache_creation_input_tokens') AS cache_creation_input_tokens
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
                llm_token_prices.cache_read_input_token_cost,
                llm_token_prices.cache_creation_input_token_cost,
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
                                          AND ((llm_token_prices.pricing_level_id = {pb_4:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_5:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_6:String})))) -- Final Select, which just selects the correct fields, and adds a costs object
        SELECT id,
               started_at,
               `summary.weave.trace_name`,
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',',
                                        '"cache_read_input_tokens":', toString(cache_read_input_tokens), ',',
                                        '"cache_creation_input_tokens":', toString(cache_creation_input_tokens), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',',
                                        '"cache_read_input_token_cost":', toString(cache_read_input_token_cost), ',',
                                        '"cache_creation_input_token_cost":', toString(cache_creation_input_token_cost), ',',
                                        '"prompt_tokens_total_cost":', toString((prompt_tokens - cache_read_input_tokens - cache_creation_input_tokens) * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',',
                                        '"cache_read_input_tokens_total_cost":', toString(cache_read_input_tokens * cache_read_input_token_cost), ',',
                                        '"cache_creation_input_tokens_total_cost":', toString(cache_creation_input_tokens * cache_creation_input_token_cost), ',',
                                        '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }'), '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_7:UInt64})
        GROUP BY id,
                 started_at,
                 `summary.weave.trace_name`
        ORDER BY `summary.weave.trace_name` DESC
        """,
            {
                "pb_0": "",
                "pb_1": SENTINEL_EPOCH,
                "pb_2": "",
                "pb_3": "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
                "pb_4": "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
                "pb_5": "default",
                "pb_6": "",
                "pb_7": 1,
            },
            id="test_query_calls_complete_with_costs_and_trace_name_order",
        ),
    ],
)
def test_query_with_costs_calls_complete_order(
    orders: list[tuple[str, str]], expected_sql: str, expected_params: dict
) -> None:
    cq = CallsQuery(
        project_id=PROJECT_COMPLETE,
        include_costs=True,
        read_table=ReadTable.CALLS_COMPLETE,
    )
    cq.add_field("id")
    cq.add_field("started_at")
    for field, direction in orders:
        cq.add_order(field, direction)
    assert_sql(cq, expected_sql, expected_params)


def test_query_with_costs_and_summary_weave_trace_name_field() -> None:
    """Test that summary.weave.trace_name is backtick-quoted when used with costs."""
    cq = CallsQuery(
        project_id="UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=", include_costs=True
    )
    cq.add_field("id")
    cq.add_field("summary.weave.trace_name")
    cq.add_field("started_at")

    assert_sql(
        cq,
        """
        WITH filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged PREWHERE calls_merged.project_id = {pb_0:String}
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.op_name) IS NULL)))))),
             all_calls AS
          (SELECT calls_merged.id AS id,
                  CASE
                      WHEN argMaxMerge(calls_merged.display_name) IS NOT NULL
                           AND argMaxMerge(calls_merged.display_name) != '' THEN argMaxMerge(calls_merged.display_name)
                      WHEN any(calls_merged.op_name) IS NOT NULL
                           AND any(calls_merged.op_name) LIKE 'weave-trace-internal:///%' THEN regexpExtract(toString(any(calls_merged.op_name)), '/([^/:]*):', 1)
                      ELSE any(calls_merged.op_name)
                  END AS `summary.weave.trace_name`,
                  any(calls_merged.started_at) AS started_at
           FROM calls_merged PREWHERE calls_merged.project_id = {pb_0:String}
           WHERE (calls_merged.id IN filtered_calls)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)),
             llm_usage AS
          (-- From the all_calls we get the usage data for LLMs
         SELECT *,
                ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
                arrayJoin(if(usage_raw != ''
                             and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\\"requests\\": 0, \\"prompt_tokens\\": 0, \\"completion_tokens\\": 0, \\"total_tokens\\": 0, \\"cache_read_input_tokens\\": 0, \\"cache_creation_input_tokens\\": 0}')])) AS kv,
                kv.1 AS llm_id,
                JSONExtractInt(kv.2, 'requests') AS requests,
                (if(JSONHas(kv.2, 'prompt_tokens'), JSONExtractInt(kv.2, 'prompt_tokens'), 0) + if(JSONHas(kv.2, 'input_tokens'), JSONExtractInt(kv.2, 'input_tokens'), 0)) AS prompt_tokens,
                (if(JSONHas(kv.2, 'completion_tokens'), JSONExtractInt(kv.2, 'completion_tokens'), 0) + if(JSONHas(kv.2, 'output_tokens'), JSONExtractInt(kv.2, 'output_tokens'), 0)) AS completion_tokens,
                JSONExtractInt(kv.2, 'total_tokens') AS total_tokens,
                JSONExtractInt(kv.2, 'cache_read_input_tokens') AS cache_read_input_tokens,
                JSONExtractInt(kv.2, 'cache_creation_input_tokens') AS cache_creation_input_tokens
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
                llm_token_prices.cache_read_input_token_cost,
                llm_token_prices.cache_creation_input_token_cost,
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
                                          AND ((llm_token_prices.pricing_level_id = {pb_1:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_2:String})
                                               OR (llm_token_prices.pricing_level_id = {pb_3:String})))) -- Final Select, which just selects the correct fields, and adds a costs object
        SELECT id,
               `summary.weave.trace_name`,
               started_at,
               if(any(llm_id) = 'weave_dummy_llm_id'
                  or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',',
                                        '"cache_read_input_tokens":', toString(cache_read_input_tokens), ',',
                                        '"cache_creation_input_tokens":', toString(cache_creation_input_tokens), ',',
                                        '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',',
                                        '"cache_read_input_token_cost":', toString(cache_read_input_token_cost), ',',
                                        '"cache_creation_input_token_cost":', toString(cache_creation_input_token_cost), ',',
                                        '"prompt_tokens_total_cost":', toString((prompt_tokens - cache_read_input_tokens - cache_creation_input_tokens) * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',',
                                        '"cache_read_input_tokens_total_cost":', toString(cache_read_input_tokens * cache_read_input_token_cost), ',',
                                        '"cache_creation_input_tokens_total_cost":', toString(cache_creation_input_tokens * cache_creation_input_token_cost), ',',
                                        '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }'), '}')) AS summary_dump
        FROM ranked_prices
        WHERE (rank = {pb_4:UInt64})
        GROUP BY id,
                 `summary.weave.trace_name`,
                 started_at
        """,
        {
            "pb_0": "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
            "pb_1": "UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=",
            "pb_2": "default",
            "pb_3": "",
            "pb_4": 1,
        },
    )
