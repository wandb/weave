-- Add cost and token aggregation columns to existing calls_merged_stats table
-- Note: We cannot use aggregate function states as default values in ClickHouse
ALTER TABLE calls_merged_stats ADD COLUMN IF NOT EXISTS total_prompt_tokens SimpleAggregateFunction(sum, UInt64);
ALTER TABLE calls_merged_stats ADD COLUMN IF NOT EXISTS total_completion_tokens SimpleAggregateFunction(sum, UInt64);
ALTER TABLE calls_merged_stats ADD COLUMN IF NOT EXISTS total_tokens SimpleAggregateFunction(sum, UInt64);
ALTER TABLE calls_merged_stats ADD COLUMN IF NOT EXISTS total_requests SimpleAggregateFunction(sum, UInt64);
ALTER TABLE calls_merged_stats ADD COLUMN IF NOT EXISTS total_prompt_tokens_cost SimpleAggregateFunction(sum, Float64);
ALTER TABLE calls_merged_stats ADD COLUMN IF NOT EXISTS total_completion_tokens_cost SimpleAggregateFunction(sum, Float64);
ALTER TABLE calls_merged_stats ADD COLUMN IF NOT EXISTS total_cost SimpleAggregateFunction(sum, Float64);

-- Create a dictionary for LLM token prices lookup
-- This allows efficient price lookups in the materialized view
CREATE DICTIONARY IF NOT EXISTS llm_prices_dict
(
    pricing_key String,
    prompt_token_cost Float64,
    completion_token_cost Float64
)
PRIMARY KEY pricing_key
SOURCE(CLICKHOUSE(
    HOST 'localhost'
    PORT 9000
    USER 'default'
    QUERY 'SELECT 
        concat(pricing_level, ''|'', pricing_level_id, ''|'', provider_id, ''|'', llm_id) as pricing_key,
        prompt_token_cost,
        completion_token_cost
    FROM default.llm_token_prices
    WHERE effective_date = (
        SELECT max(effective_date) 
        FROM default.llm_token_prices AS ltp2 
        WHERE ltp2.pricing_level = llm_token_prices.pricing_level
          AND ltp2.pricing_level_id = llm_token_prices.pricing_level_id
          AND ltp2.provider_id = llm_token_prices.provider_id
          AND ltp2.llm_id = llm_token_prices.llm_id
          AND ltp2.effective_date <= now()
    )'
))
LIFETIME(MIN 300 MAX 600)
LAYOUT(HASHED());

-- Drop and recreate the materialized view to include token aggregations and cost calculations
DROP VIEW IF EXISTS calls_merged_stats_view;

CREATE MATERIALIZED VIEW calls_merged_stats_view
TO calls_merged_stats
AS
SELECT
    call_parts.project_id,
    call_parts.id,
    anySimpleState(call_parts.trace_id) as trace_id,
    anySimpleState(call_parts.parent_id) as parent_id,
    anySimpleState(call_parts.op_name) as op_name,
    anySimpleState(call_parts.started_at) as started_at,
    anySimpleState(length(call_parts.attributes_dump)) as attributes_size_bytes,
    anySimpleState(length(call_parts.inputs_dump)) as inputs_size_bytes,
    anySimpleState(call_parts.ended_at) as ended_at,
    anySimpleState(length(call_parts.output_dump)) as output_size_bytes,
    anySimpleState(length(call_parts.summary_dump)) as summary_size_bytes,
    anySimpleState(length(call_parts.exception)) as exception_size_bytes,
    anySimpleState(call_parts.wb_user_id) as wb_user_id,
    anySimpleState(call_parts.wb_run_id) as wb_run_id,
    anySimpleState(call_parts.deleted_at) as deleted_at,
    maxSimpleState(call_parts.created_at) as updated_at,
    argMaxState(call_parts.display_name, call_parts.created_at) as display_name,
    -- Aggregate token usage across all models in the usage object
    -- Use ifNull to handle case where 'usage' key doesn't exist
    sumSimpleState(
        arraySum(
            arrayMap(
                kv -> JSONExtractUInt(kv.2, 'prompt_tokens'),
                arrayFilter(
                    kv -> JSONHas(kv.2, 'prompt_tokens'),
                    JSONExtractKeysAndValuesRaw(ifNull(JSONExtractRaw(call_parts.summary_dump, 'usage'), '{}'))
                )
            )
        )
    ) as total_prompt_tokens,
    sumSimpleState(
        arraySum(
            arrayMap(
                kv -> JSONExtractUInt(kv.2, 'completion_tokens'),
                arrayFilter(
                    kv -> JSONHas(kv.2, 'completion_tokens'),
                    JSONExtractKeysAndValuesRaw(ifNull(JSONExtractRaw(call_parts.summary_dump, 'usage'), '{}'))
                )
            )
        )
    ) as total_completion_tokens,
    sumSimpleState(
        arraySum(
            arrayMap(
                kv -> JSONExtractUInt(kv.2, 'total_tokens'),
                arrayFilter(
                    kv -> JSONHas(kv.2, 'total_tokens'),
                    JSONExtractKeysAndValuesRaw(ifNull(JSONExtractRaw(call_parts.summary_dump, 'usage'), '{}'))
                )
            )
        )
    ) as total_tokens,
    sumSimpleState(
        arraySum(
            arrayMap(
                kv -> JSONExtractUInt(kv.2, 'requests'),
                arrayFilter(
                    kv -> JSONHas(kv.2, 'requests'),
                    JSONExtractKeysAndValuesRaw(ifNull(JSONExtractRaw(call_parts.summary_dump, 'usage'), '{}'))
                )
            )
        )
    ) as total_requests,
    -- Calculate costs using dictionary lookups
    -- We'll try multiple pricing levels: project-specific, then org-specific, then default
    sumSimpleState(
        arraySum(
            arrayMap(
                kv -> (
                    JSONExtractUInt(kv.2, 'prompt_tokens') * 
                    -- Extract provider and model from the key (format: provider:model)
                    dictGetOrDefault('llm_prices_dict', 'prompt_token_cost',
                        -- Try project-level pricing first
                        concat('project|', call_parts.project_id, '|', 
                            splitByChar(':', kv.1)[1], '|',  -- provider
                            splitByChar(':', kv.1)[2]   -- model
                        ),
                        -- Fall back to default pricing
                        dictGetOrDefault('llm_prices_dict', 'prompt_token_cost',
                            concat('default|default|',
                                splitByChar(':', kv.1)[1], '|',  -- provider
                                splitByChar(':', kv.1)[2]   -- model
                            ),
                            0.0  -- Default if no pricing found
                        )
                    )
                ),
                arrayFilter(
                    kv -> JSONHas(kv.2, 'prompt_tokens'),
                    JSONExtractKeysAndValuesRaw(ifNull(JSONExtractRaw(call_parts.summary_dump, 'usage'), '{}'))
                )
            )
        )
    ) as total_prompt_tokens_cost,
    sumSimpleState(
        arraySum(
            arrayMap(
                kv -> (
                    JSONExtractUInt(kv.2, 'completion_tokens') * 
                    dictGetOrDefault('llm_prices_dict', 'completion_token_cost',
                        -- Try project-level pricing first
                        concat('project|', call_parts.project_id, '|', 
                            splitByChar(':', kv.1)[1], '|',  -- provider
                            splitByChar(':', kv.1)[2]   -- model
                        ),
                        -- Fall back to default pricing
                        dictGetOrDefault('llm_prices_dict', 'completion_token_cost',
                            concat('default|default|',
                                splitByChar(':', kv.1)[1], '|',  -- provider
                                splitByChar(':', kv.1)[2]   -- model
                            ),
                            0.0  -- Default if no pricing found
                        )
                    )
                ),
                arrayFilter(
                    kv -> JSONHas(kv.2, 'completion_tokens'),
                    JSONExtractKeysAndValuesRaw(ifNull(JSONExtractRaw(call_parts.summary_dump, 'usage'), '{}'))
                )
            )
        )
    ) as total_completion_tokens_cost,
    -- Total cost is sum of prompt and completion costs
    sumSimpleState(
        arraySum(
            arrayMap(
                kv -> (
                    JSONExtractUInt(kv.2, 'prompt_tokens') * 
                    dictGetOrDefault('llm_prices_dict', 'prompt_token_cost',
                        concat('project|', call_parts.project_id, '|', 
                            splitByChar(':', kv.1)[1], '|',
                            splitByChar(':', kv.1)[2]
                        ),
                        dictGetOrDefault('llm_prices_dict', 'prompt_token_cost',
                            concat('default|default|',
                                splitByChar(':', kv.1)[1], '|',
                                splitByChar(':', kv.1)[2]
                            ),
                            0.0
                        )
                    ) +
                    JSONExtractUInt(kv.2, 'completion_tokens') * 
                    dictGetOrDefault('llm_prices_dict', 'completion_token_cost',
                        concat('project|', call_parts.project_id, '|', 
                            splitByChar(':', kv.1)[1], '|',
                            splitByChar(':', kv.1)[2]
                        ),
                        dictGetOrDefault('llm_prices_dict', 'completion_token_cost',
                            concat('default|default|',
                                splitByChar(':', kv.1)[1], '|',
                                splitByChar(':', kv.1)[2]
                            ),
                            0.0
                        )
                    )
                ),
                arrayFilter(
                    kv -> (JSONHas(kv.2, 'prompt_tokens') OR JSONHas(kv.2, 'completion_tokens')),
                    JSONExtractKeysAndValuesRaw(ifNull(JSONExtractRaw(call_parts.summary_dump, 'usage'), '{}'))
                )
            )
        )
    ) as total_cost
FROM call_parts
GROUP BY
    call_parts.project_id,
    call_parts.id; 