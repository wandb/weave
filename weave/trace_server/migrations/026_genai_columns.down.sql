-- Reverse of 026_genai_columns.up.sql

-- Drop indexes first
ALTER TABLE calls_complete DROP INDEX IF EXISTS idx_operation_name;
ALTER TABLE calls_complete DROP INDEX IF EXISTS idx_provider_name;
ALTER TABLE calls_complete DROP INDEX IF EXISTS idx_request_model;
ALTER TABLE calls_complete DROP INDEX IF EXISTS idx_conversation_id;
ALTER TABLE calls_complete DROP INDEX IF EXISTS idx_agent_name;
ALTER TABLE calls_complete DROP INDEX IF EXISTS idx_tool_name;

-- Drop columns
ALTER TABLE calls_complete DROP COLUMN IF EXISTS operation_name;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS provider_name;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS request_model;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS response_model;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS response_id;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS input_tokens;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS output_tokens;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS total_tokens;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS reasoning_tokens;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS request_temperature;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS request_max_tokens;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS request_top_p;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS conversation_id;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS agent_name;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS tool_name;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS input_messages;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS output_messages;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS finish_reasons;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS system_instructions;
ALTER TABLE calls_complete DROP COLUMN IF EXISTS tool_call_arguments;
