-- Drop the materialized view
DROP VIEW IF EXISTS calls_merged_stats_view;

-- Drop the dictionary
DROP DICTIONARY IF EXISTS llm_prices_dict;

-- Remove the cost and token aggregation columns
ALTER TABLE calls_merged_stats DROP COLUMN IF EXISTS total_prompt_tokens;
ALTER TABLE calls_merged_stats DROP COLUMN IF EXISTS total_completion_tokens;
ALTER TABLE calls_merged_stats DROP COLUMN IF EXISTS total_tokens;
ALTER TABLE calls_merged_stats DROP COLUMN IF EXISTS total_requests;
ALTER TABLE calls_merged_stats DROP COLUMN IF EXISTS total_prompt_tokens_cost;
ALTER TABLE calls_merged_stats DROP COLUMN IF EXISTS total_completion_tokens_cost;
ALTER TABLE calls_merged_stats DROP COLUMN IF EXISTS total_cost;

-- Recreate the original materialized view without cost calculations
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
    argMaxState(call_parts.display_name, call_parts.created_at) as display_name
FROM call_parts
GROUP BY
    call_parts.project_id,
    call_parts.id; 