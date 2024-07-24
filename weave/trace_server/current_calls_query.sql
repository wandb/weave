-- This is the current call stream query

-- We get the lightly filtered call ids
-- Then we get the calls with the heavy filters
-- From the 100 limited calls we get their usage data
-- From the llm ids in the usage data we get the prices and rank them
-- We get the top ranked prices and discard the rest
-- We join the top ranked prices with the usage data to get the token costs
-- Finally we pull all the data from the calls and add a costs object

-- First we get lightly filtered calls, to optimize later for heavy filters
WITH 
    filtered_calls AS (
        SELECT calls_merged.id AS id
        FROM calls_merged
        WHERE project_id = {pb_2_1:String}
        AND (id IN {pb_2_2:Array(String)})
        GROUP BY (project_id,
                id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
                AND (calls_merged.id IN {pb_2_0:Array(String)}))
        ORDER BY any(calls_merged.started_at) ASC
        LIMIT 1),

                -- Then we get all the calls we want, with all the data we need, with heavy filtering
                all_calls AS (
        SELECT calls_merged.project_id AS project_id,
            calls_merged.id AS id,
            any(calls_merged.op_name) AS op_name,
            argMaxMerge(calls_merged.display_name) AS display_name,
            any(calls_merged.trace_id) AS trace_id,
            any(calls_merged.parent_id) AS parent_id,
            any(calls_merged.started_at) AS started_at,
            any(calls_merged.ended_at) AS ended_at,
            any(calls_merged.exception) AS
        exception,
            array_concat_agg(calls_merged.input_refs) AS input_refs,
            array_concat_agg(calls_merged.output_refs) AS output_refs,
            any(calls_merged.wb_user_id) AS wb_user_id,
            any(calls_merged.wb_run_id) AS wb_run_id,
            any(calls_merged.deleted_at) AS deleted_at,
            any(calls_merged.attributes_dump) AS attributes_dump,
            any(calls_merged.inputs_dump) AS inputs_dump,
            any(calls_merged.output_dump) AS output_dump,
            any(calls_merged.summary_dump) AS summary_dump
        FROM calls_merged
        WHERE project_id = {pb_2_3:String}
        AND (id IN filtered_calls)
        GROUP BY (project_id,
                id)
        ORDER BY any(calls_merged.started_at) ASC),

    -- From the all_calls we get the usage data for LLMs
    -- Generate a list of LLM IDs and their respective token counts from the JSON structure
    llm_usage AS (
        
        SELECT
            id,
            started_at,
            ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') AS usage_raw,
            arrayJoin(
                arrayMap(
                    kv -> (kv.1, kv.2),
                    JSONExtractKeysAndValuesRaw(usage_raw)
                )
            ) AS kv,
            kv.1 AS llm_id,
            JSONExtractInt(kv.2, 'requests') AS requests,
            -- Some libraries return input_tokens and output_tokens, others prompt_tokens and completion_tokens
            if(
                JSONHas(kv.2, 'prompt_tokens'),
                JSONExtractInt(kv.2, 'prompt_tokens'),
                JSONExtractInt(kv.2, 'input_tokens')
            ) AS prompt_tokens,
            if(
                JSONHas(kv.2, 'completion_tokens'),
                JSONExtractInt(kv.2, 'completion_tokens'),
                JSONExtractInt(kv.2, 'output_tokens')
            ) AS completion_tokens,
            JSONExtractInt(kv.2, 'total_tokens') AS total_tokens
        FROM
            all_calls
        WHERE
            JSONLength(usage_raw) > 0
    
    ),

    -- based on the llm_ids in the usage data we get all the prices and rank them
    -- Rank the rows in llm_token_prices based on the given conditions and effective_date
    ranked_prices AS (
        
        SELECT
            lu.id,
            lu.llm_id,
            lu.started_at,
            ltp.input_token_cost,
            ltp.output_token_cost,
            ltp.effective_date,
            ltp.pricing_level,
            ltp.pricing_level_id,
            ltp.provider_id,
            lu.requests,
            ROW_NUMBER() OVER (
                PARTITION BY lu.id, lu.llm_id
                ORDER BY
                    CASE
                        -- Order by pricing level then by effective_date
                        -- WHEN ltp.pricing_level = 'org' AND ltp.pricing_level_id = ORG_NAME THEN 1
                        WHEN ltp.pricing_level = 'project' AND ltp.pricing_level_id = 'UHJvamVjdEludGVybmFsSWQ6Mzk3MDA1MjA=' THEN 2
                        WHEN ltp.pricing_level = 'default' AND ltp.pricing_level_id = 'default' THEN 3
                        ELSE 4
                    END,
                    ltp.effective_date DESC
            ) AS rank
        FROM
            llm_usage AS lu
        LEFT JOIN
            llm_token_prices AS ltp
        ON
            lu.llm_id = ltp.llm_id
        WHERE
            ltp.effective_date <= lu.started_at
    
    ),

    -- Discard all but the top-ranked prices
    -- Filter to get the top-ranked prices for each llm_id and call id
    top_ranked_prices AS (
        
        SELECT
            id,
            llm_id,
            input_token_cost,
            output_token_cost,
            effective_date,
            pricing_level,
            pricing_level_id,
            provider_id
        FROM
            ranked_prices
        WHERE
            rank = 1
    
    ),

    -- Join with the top-ranked prices to get the token costs
    usage_with_costs AS (
        
            SELECT
            lu.id,
            lu.llm_id,
            lu.requests,
            lu.prompt_tokens,
            lu.completion_tokens,
            lu.total_tokens,
            lu.requests,
            trp.effective_date,
            trp.pricing_level,
            trp.pricing_level_id,
            trp.input_token_cost AS prompt_token_cost,
            trp.output_token_cost AS completion_token_cost,
            trp.provider_id,
            prompt_tokens * prompt_token_cost AS prompt_tokens_cost,
            completion_tokens * completion_token_cost AS completion_tokens_cost
        FROM
            llm_usage AS lu
        LEFT JOIN
            top_ranked_prices AS trp
        ON
            lu.id = trp.id AND lu.llm_id = trp.llm_id
    
    )

    -- Final Select, which just pulls all the data from all_calls, and adds a costs object
    SELECT all_calls.project_id AS project_id, all_calls.id AS id, any(all_calls.op_name) AS op_name, all_calls.display_name, any(all_calls.trace_id) AS trace_id, any(all_calls.parent_id) AS parent_id, any(all_calls.started_at) AS started_at, any(all_calls.ended_at) AS ended_at, any(all_calls.exception) AS exception, array_concat_agg(all_calls.input_refs) AS input_refs, array_concat_agg(all_calls.output_refs) AS output_refs, any(all_calls.wb_user_id) AS wb_user_id, any(all_calls.wb_run_id) AS wb_run_id, any(all_calls.deleted_at) AS deleted_at, any(all_calls.attributes_dump) AS attributes_dump, any(all_calls.inputs_dump) AS inputs_dump, any(all_calls.output_dump) AS output_dump,

    -- Creates the cost object as a JSON string
    concat(
        -- Remove the last closing brace
        left(any(all_calls.summary_dump), length(any(all_calls.summary_dump)) - 1),
        ',"costs":',
        concat('{', arrayStringConcat(groupUniqArray(
            concat('"', llm_id, '":{',
                '"prompt_tokens":', toString(prompt_tokens), ',',
                '"prompt_tokens_cost":', toString(prompt_tokens_cost), ',',
                '"completion_tokens_cost":', toString(completion_tokens_cost), ',',
                '"completion_tokens":', toString(completion_tokens), ',',
                '"prompt_token_cost":', toString(prompt_token_cost), ',',
                '"completion_token_cost":', toString(completion_token_cost), ',',
                '"total_tokens":', toString(total_tokens), ',',
                '"requests":', toString(requests), ',',
                '"effective_date":"', toString(effective_date), '",',
                '"provider_id":"', toString(provider_id), '",',
                '"pricing_level":"', toString(pricing_level), '",',
                '"pricing_level_id":"', toString(pricing_level_id), '"}')
        ), ','), '}'),
    '}'
    ) AS summary_dump

    FROM all_calls
    JOIN usage_with_costs
        ON all_calls.id = usage_with_costs.id
    GROUP BY (all_calls.id, all_calls.project_id, all_calls.display_name)
