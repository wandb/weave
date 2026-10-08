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
 SELECT id,
        started_at,
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
   FROM llm_usage GLOBAL
   LEFT JOIN llm_token_prices ON ((llm_usage.llm_id = llm_token_prices.llm_id)
                                  AND ((llm_token_prices.pricing_level_id = {pb_1:String})
                                       OR (llm_token_prices.pricing_level_id = {pb_2:String})
                                       OR (llm_token_prices.pricing_level_id = {pb_3:String})))),
     call_costs AS
  (-- Final Select, which just selects the correct fields, and adds a costs object
SELECT id,
       if(any(llm_id) = 'weave_dummy_llm_id'
          or any(llm_token_prices.id) == '', '', concat(',"weave":{', '"costs":', concat('{', arrayStringConcat(groupUniqArray(concat('"', toString(llm_id), '":{', '"prompt_tokens":', toString(prompt_tokens), ',', '"completion_tokens":', toString(completion_tokens), ',', '"requests":', toString(requests), ',', '"total_tokens":', toString(total_tokens), ',', '"cache_read_input_tokens":', toString(cache_read_input_tokens), ',', '"cache_creation_input_tokens":', toString(cache_creation_input_tokens), ',', '"prompt_token_cost":', toString(prompt_token_cost), ',', '"completion_token_cost":', toString(completion_token_cost), ',', '"cache_read_input_token_cost":', toString(cache_read_input_token_cost), ',', '"cache_creation_input_token_cost":', toString(cache_creation_input_token_cost), ',', '"prompt_tokens_total_cost":', toString((prompt_tokens - cache_read_input_tokens - cache_creation_input_tokens) * prompt_token_cost), ',', '"completion_tokens_total_cost":', toString(completion_tokens * completion_token_cost), ',', '"cache_read_input_tokens_total_cost":', toString(cache_read_input_tokens * cache_read_input_token_cost), ',', '"cache_creation_input_tokens_total_cost":', toString(cache_creation_input_tokens * cache_creation_input_token_cost), ',', '"prompt_token_cost_unit":"', toString(prompt_token_cost_unit), '",', '"completion_token_cost_unit":"', toString(completion_token_cost_unit), '",', '"effective_date":"', toString(effective_date), '",', '"provider_id":"', toString(provider_id), '",', '"pricing_level":"', toString(pricing_level), '",', '"pricing_level_id":"', toString(pricing_level_id), '",', '"created_by":"', toString(created_by), '",', '"created_at":"', toString(created_at), '"}')), ','), '} }'))) AS cost_fragment
   FROM ranked_prices
   WHERE (rank = {pb_4:UInt64})
   GROUP BY id)
SELECT *
FROM
  (SELECT all_calls.id AS id,
          all_calls.project_id AS project_id,
          all_calls.trace_id AS trace_id,
          all_calls.parent_id AS parent_id,
          all_calls.op_name AS op_name,
          all_calls.started_at AS started_at,
          all_calls.ended_at AS ended_at,
          all_calls.exception AS
   exception,
          all_calls.display_name AS display_name,
          all_calls.inputs_dump AS inputs_dump,
          all_calls.output_dump AS output_dump,
          all_calls.attributes_dump AS attributes_dump,
          if(call_costs.cost_fragment = '', all_calls.summary_dump, concat(left(all_calls.summary_dump, length(all_calls.summary_dump) - 1), call_costs.cost_fragment, '}')) AS summary_dump
   FROM all_calls GLOBAL
   INNER JOIN call_costs ON all_calls.id = call_costs.id) AS cost_enriched_calls
ORDER BY cost_enriched_calls.started_at DESC,
         cost_enriched_calls.id ASC
