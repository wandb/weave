WITH filtered_calls AS
  (SELECT calls_merged.id AS id
   FROM calls_merged PREWHERE calls_merged.project_id = {pb_0:String}
   GROUP BY (calls_merged.project_id,
             calls_merged.id)
   HAVING (((any(calls_merged.deleted_at) IS NULL))
           AND ((NOT ((any(calls_merged.op_name) IS NULL)))))
   ORDER BY any(calls_merged.started_at) DESC, calls_merged.id ASC
   LIMIT 2
   OFFSET 1),
     all_calls AS
  (SELECT calls_merged.id AS id,
          calls_merged.project_id AS project_id,
          any(calls_merged.trace_id) AS trace_id,
          any(calls_merged.parent_id) AS parent_id,
          any(calls_merged.op_name) AS op_name,
          any(calls_merged.started_at) AS started_at,
          any(calls_merged.ended_at) AS ended_at,
          any(calls_merged.exception) AS
   exception,
          argMaxMerge(calls_merged.display_name) AS display_name,
          any(calls_merged.inputs_dump) AS inputs_dump,
          any(calls_merged.output_dump) AS output_dump,
          any(calls_merged.attributes_dump) AS attributes_dump,
          any(calls_merged.summary_dump) AS summary_dump
   FROM calls_merged PREWHERE calls_merged.project_id = {pb_0:String}
   WHERE (calls_merged.id IN filtered_calls)
   GROUP BY (calls_merged.project_id,
             calls_merged.id)
   ORDER BY any(calls_merged.started_at) DESC, calls_merged.id ASC),
     llm_usage AS
  (-- From the all_calls we get the usage data for LLMs
 SELECT *,
        ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
        arrayJoin(if(usage_raw != ''
                     and usage_raw != '{}', JSONExtractKeysAndValuesRaw(usage_raw), [('weave_dummy_llm_id', '{\"requests\": 0, \"prompt_tokens\": 0, \"completion_tokens\": 0, \"total_tokens\": 0, \"cache_read_input_tokens\": 0, \"cache_creation_input_tokens\": 0}')])) AS kv,
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
 SELECT llm_usage.*,
        best_price.1 AS `llm_token_prices.id`,
        best_price.2 AS pricing_level,
        best_price.3 AS pricing_level_id,
        best_price.4 AS provider_id,
        best_price.5 AS `llm_token_prices.llm_id`,
        best_price.6 AS effective_date,
        best_price.7 AS prompt_token_cost,
        best_price.8 AS completion_token_cost,
        best_price.9 AS cache_read_input_token_cost,
        best_price.10 AS cache_creation_input_token_cost,
        best_price.11 AS prompt_token_cost_unit,
        best_price.12 AS completion_token_cost_unit,
        best_price.13 AS created_by,
        best_price.14 AS created_at,
        ROW_NUMBER() OVER (PARTITION BY llm_usage.id, llm_usage.llm_id
                           ORDER BY if(llm_usage.started_at >= best_price.6, 1, 2), multiIf(best_price.2 = 'project'
                                                                                            AND best_price.3 = {pb_0:String}, 2, best_price.2 = 'default'
                                                                                            AND best_price.3 = {pb_1:String}, 3, 4), best_price.6 DESC) AS rank
   FROM llm_usage GLOBAL
   LEFT JOIN
     (SELECT llm_id,
             arraySort(price -> tuple(multiIf(price.2 = 'project'
                                              AND price.3 = {pb_0:String}, 2, price.2 = 'default'
                                              AND price.3 = {pb_1:String}, 3, 4), -toUnixTimestamp64Micro(toDateTime64(price.6, 6))), groupArray(tuple(id, pricing_level, pricing_level_id, provider_id, llm_id, effective_date, prompt_token_cost, completion_token_cost, cache_read_input_token_cost, cache_creation_input_token_cost, prompt_token_cost_unit, completion_token_cost_unit, created_by, created_at))) AS price_history
      FROM llm_token_prices
      WHERE pricing_level_id IN ({pb_0:String}, {pb_1:String}, {pb_2:String})
      GROUP BY llm_id) AS model_prices ON llm_usage.llm_id = model_prices.llm_id LEFT ARRAY
   JOIN [arrayElement(price_history, greatest(arrayFirstIndex(
    price -> llm_usage.started_at >= price.6, price_history
), 1))] AS best_price) -- Final Select, which just selects the correct fields, and adds a costs object

SELECT id,
       project_id,
       trace_id,
       parent_id,
       op_name,
       started_at,
       ended_at,
exception,
       display_name,
       inputs_dump,
       output_dump,
       attributes_dump,
       if(any(llm_id) = 'weave_dummy_llm_id'
          or any(llm_token_prices.id) == '', any(summary_dump), concat(left(any(summary_dump), length(any(summary_dump)) - 1), ',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"cache_read_input_tokens":', toString(cache_read_input_tokens), ',', '"cache_creation_input_tokens":', toString(cache_creation_input_tokens), ',', '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',', '"cache_read_input_token_cost":', toString(cache_read_input_token_cost), ',', '"cache_creation_input_token_cost":', toString(cache_creation_input_token_cost), ',', '"prompt_tokens_total_cost":', toString((prompt_tokens - cache_read_input_tokens - cache_creation_input_tokens) * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"cache_read_input_tokens_total_cost":', toString(cache_read_input_tokens * cache_read_input_token_cost), ',', '"cache_creation_input_tokens_total_cost":', toString(cache_creation_input_tokens * cache_creation_input_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }') , '}')) AS summary_dump
FROM ranked_prices
WHERE (rank = {pb_3:UInt64})
GROUP BY id,
         project_id,
         trace_id,
         parent_id,
         op_name,
         started_at,
         ended_at,
exception,
         display_name,
         inputs_dump,
         output_dump,
         attributes_dump
ORDER BY ranked_prices.started_at DESC,
         ranked_prices.id ASC
