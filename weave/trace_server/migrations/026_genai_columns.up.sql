ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    operation_name LowCardinality(String) DEFAULT '';

ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    provider_name LowCardinality(String) DEFAULT '';

-- Model info
ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    request_model String DEFAULT '';

ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    response_model String DEFAULT '';

ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    response_id String DEFAULT '';

-- Token usage
ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    input_tokens UInt64 DEFAULT 0;

ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    output_tokens UInt64 DEFAULT 0;

ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    total_tokens UInt64 DEFAULT 0;

ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    reasoning_tokens UInt64 DEFAULT 0;

-- Request parameters
ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    request_temperature Float64 DEFAULT 0;

ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    request_max_tokens UInt64 DEFAULT 0;

ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    request_top_p Float64 DEFAULT 0;

-- Session / conversation
ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    conversation_id String DEFAULT '';

-- Agent info
ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    agent_name String DEFAULT '';

-- Tool info
ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    tool_name String DEFAULT '';


-- ---------------------------------------------------------------------------
-- 2. Message arrays (normalized from any provider format at ingest time)
-- ---------------------------------------------------------------------------

ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    input_messages Array(Tuple(
        role LowCardinality(String),
        content String,
        tool_call_id String,
        tool_name String
    )) DEFAULT [];

ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    output_messages Array(Tuple(
        role LowCardinality(String),
        content String,
        tool_call_id String,
        tool_name String
    )) DEFAULT [];


-- ---------------------------------------------------------------------------
-- 3. Additional metadata
-- ---------------------------------------------------------------------------

ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    finish_reasons Array(String) DEFAULT [];

ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    system_instructions Array(String) DEFAULT [];

ALTER TABLE calls_complete ADD COLUMN IF NOT EXISTS
    tool_call_arguments String DEFAULT '';


-- ---------------------------------------------------------------------------
-- 4. Skip indexes for common GenAI filter patterns
-- ---------------------------------------------------------------------------

ALTER TABLE calls_complete ADD INDEX IF NOT EXISTS
    idx_operation_name operation_name TYPE set(20) GRANULARITY 4;

ALTER TABLE calls_complete ADD INDEX IF NOT EXISTS
    idx_provider_name provider_name TYPE set(20) GRANULARITY 4;

ALTER TABLE calls_complete ADD INDEX IF NOT EXISTS
    idx_request_model request_model TYPE set(100) GRANULARITY 4;

ALTER TABLE calls_complete ADD INDEX IF NOT EXISTS
    idx_conversation_id conversation_id TYPE set(100) GRANULARITY 4;

ALTER TABLE calls_complete ADD INDEX IF NOT EXISTS
    idx_agent_name agent_name TYPE set(100) GRANULARITY 4;

ALTER TABLE calls_complete ADD INDEX IF NOT EXISTS
    idx_tool_name tool_name TYPE set(100) GRANULARITY 4;
