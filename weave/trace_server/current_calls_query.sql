WITH 
    filtered_calls AS (
        SELECT calls_merged.id AS id
        FROM calls_merged
        WHERE project_id = {pb_25_0:String}
        GROUP BY (project_id,
                id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
                AND (any(calls_merged.parent_id) IS NULL))
        ORDER BY any(calls_merged.started_at) DESC
        LIMIT 100
        OFFSET 0),
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
            any(calls_merged.attributes_dump) AS attributes_dump,
            any(calls_merged.inputs_dump) AS inputs_dump,
            any(calls_merged.output_dump) AS output_dump,
            any(calls_merged.summary_dump) AS summary_dump,
            array_concat_agg(calls_merged.input_refs) AS input_refs,
            array_concat_agg(calls_merged.output_refs) AS output_refs,
            any(calls_merged.wb_user_id) AS wb_user_id,
            any(calls_merged.wb_run_id) AS wb_run_id,
            any(calls_merged.deleted_at) AS deleted_at
        FROM calls_merged
        WHERE project_id = {pb_25_1:String}
        AND (id IN filtered_calls)
        GROUP BY (project_id,
                id)
        ORDER BY any(calls_merged.started_at) DESC),
    calls_with_usage AS (
        SELECT
            id,
            started_at,
            summary_dump,
        FROM
            all_calls
    ),
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
            toFloat64OrZero(toString(JSONExtractInt(kv.2, 'requests'))) AS requests,
            toFloat64OrZero(toString(JSONExtractInt(kv.2, 'prompt_tokens'))) AS prompt_tokens,
            toFloat64OrZero(toString(JSONExtractInt(kv.2, 'completion_tokens'))) AS completion_tokens,
            toFloat64OrZero(toString(JSONExtractInt(kv.2, 'total_tokens'))) AS total_tokens
        FROM
            calls_with_usage
        WHERE
            JSONLength(usage_raw) > 0
    ),
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
            ltp.filter_id,
            ROW_NUMBER() OVER (
                PARTITION BY lu.id, lu.llm_id
                ORDER BY 
                    CASE 
                        -- Order by pricing level then by effective_date
                        -- WHEN ltp.pricing_level = 'org' AND ltp.filter_id = ORG_NAME THEN 1
                        WHEN ltp.pricing_level = 'project' AND ltp.filter_id = 'UHJvamVjdEludGVybmFsSWQ6Mzk1NDg2Mjc=' THEN 2
                        WHEN ltp.pricing_level = 'default' AND ltp.filter_id = 'default' THEN 3
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
    -- Filter to get the top-ranked prices for each llm_id and call id
    top_ranked_prices AS (
        SELECT
            id,
            llm_id,
            input_token_cost,
            output_token_cost,
            effective_date,
            pricing_level,
            filter_id
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
            trp.effective_date,
            trp.pricing_level,
            trp.filter_id,
            toFloat64OrZero(toString(trp.input_token_cost)) AS prompt_token_cost,
            toFloat64OrZero(toString(trp.output_token_cost)) AS completion_token_cost,
            prompt_tokens * prompt_token_cost AS prompt_tokens_cost,
            completion_tokens * completion_token_cost AS completion_tokens_cost
        FROM
            llm_usage AS lu
        LEFT JOIN
            top_ranked_prices AS trp
        ON
            lu.id = trp.id AND lu.llm_id = trp.llm_id
    )
SELECT 
    all_calls.project_id AS project_id, 
    all_calls.id AS id, 
    any(all_calls.op_name) AS op_name, 
    all_calls.display_name, 
    any(all_calls.trace_id) AS trace_id, 
    any(all_calls.parent_id) AS parent_id, 
    any(all_calls.started_at) AS started_at, 
    any(all_calls.ended_at) AS ended_at, 
    any(all_calls.exception) AS exception, 
    any(all_calls.attributes_dump) AS attributes_dump, 
    any(all_calls.inputs_dump) AS inputs_dump, 
    any(all_calls.output_dump) AS output_dump, 
    any(all_calls.summary_dump) AS summary_dump, 
    array_concat_agg(all_calls.input_refs) AS input_refs, 
    array_concat_agg(all_calls.output_refs) AS output_refs, 
    any(all_calls.wb_user_id) AS wb_user_id, 
    any(all_calls.wb_run_id) AS wb_run_id, 
    any(all_calls.deleted_at) AS deleted_at,  
    
    concat('{', arrayStringConcat(groupUniqArray(
        concat('"', llm_id, '":{',
            '"prompt_tokens":', toString(prompt_tokens), ',',
            '"prompt_tokens_cost":', toString(prompt_tokens_cost), ',',
            '"completion_tokens_cost":', toString(completion_tokens_cost), ',',
            '"completion_tokens":', toString(completion_tokens), ',',
            '"prompt_token_cost":', toString(prompt_token_cost), ',',
            '"completion_token_cost":', toString(completion_token_cost), ',',
            '"effective_date":"', toString(effective_date), '",',
            '"pricing_level":"', toString(pricing_level), '",',
            '"filter_id":"', toString(filter_id), '"}')
    ), ','), '}') AS costs
    
    FROM all_calls
    JOIN usage_with_costs
        ON all_calls.id = usage_with_costs.id
    GROUP BY (all_calls.id, all_calls.project_id, all_calls.display_name)
