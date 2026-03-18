-- Per-agent aggregated stats, auto-populated by a MaterializedView on genai_spans inserts.
-- Uses SummingMergeTree for numeric columns and stores array columns for tool/model sets.
-- Includes placeholder columns for future LLM-generated enrichment.
CREATE TABLE IF NOT EXISTS genai_agents (
    project_id              String,
    agent_name              String,

    -- Aggregated stats (summed on merge)
    invocation_count        UInt64 DEFAULT 0,
    span_count              UInt64 DEFAULT 0,
    total_input_tokens      UInt64 DEFAULT 0,
    total_output_tokens     UInt64 DEFAULT 0,
    total_duration_ms       UInt64 DEFAULT 0,
    error_count             UInt64 DEFAULT 0,

    -- Observed metadata (latest non-empty wins via ReplacingMergeTree on created_at)
    agent_description       String DEFAULT '',
    agent_id                String DEFAULT '',
    provider_name           String DEFAULT '',
    system_instructions     String DEFAULT '',

    -- Timestamps
    first_seen              DateTime64(6),
    last_seen               DateTime64(6),

    -- Placeholder for future LLM enrichment (updated async by a worker)
    llm_summary             String DEFAULT '',
    llm_summary_updated_at  DateTime64(6) DEFAULT toDateTime64(0, 6),

    -- For dedup / merge ordering
    created_at              DateTime64(3) DEFAULT now64(3)
) ENGINE = SummingMergeTree((invocation_count, span_count, total_input_tokens, total_output_tokens, total_duration_ms, error_count))
ORDER BY (project_id, agent_name);


-- MaterializedView: on every genai_spans insert, push a row into genai_agents.
-- SummingMergeTree will accumulate the numeric columns on background merges.
-- Only spans with a non-empty agent_name are included.
CREATE MATERIALIZED VIEW IF NOT EXISTS genai_agents_mv TO genai_agents AS
SELECT
    project_id,
    agent_name,
    toUInt64(operation_name = 'invoke_agent')               AS invocation_count,
    toUInt64(1)                                              AS span_count,
    toUInt64(input_tokens)                                   AS total_input_tokens,
    toUInt64(output_tokens)                                  AS total_output_tokens,
    toUInt64(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)) AS total_duration_ms,
    toUInt64(status_code = 'ERROR')                          AS error_count,
    agent_description,
    agent_id,
    provider_name,
    system_instructions,
    started_at                                               AS first_seen,
    started_at                                               AS last_seen,
    ''                                                       AS llm_summary,
    toDateTime64(0, 6)                                       AS llm_summary_updated_at
FROM genai_spans
WHERE agent_name != '';


-- Backfill: populate genai_agents from existing genai_spans data.
-- This ensures agents from previously-ingested traces appear immediately.
INSERT INTO genai_agents
SELECT
    project_id,
    agent_name,
    toUInt64(operation_name = 'invoke_agent')               AS invocation_count,
    toUInt64(1)                                              AS span_count,
    toUInt64(input_tokens)                                   AS total_input_tokens,
    toUInt64(output_tokens)                                  AS total_output_tokens,
    toUInt64(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)) AS total_duration_ms,
    toUInt64(status_code = 'ERROR')                          AS error_count,
    agent_description,
    agent_id,
    provider_name,
    system_instructions,
    started_at                                               AS first_seen,
    started_at                                               AS last_seen,
    ''                                                       AS llm_summary,
    toDateTime64(0, 6)                                       AS llm_summary_updated_at,
    now64(3)                                                 AS created_at
FROM genai_spans
WHERE agent_name != '';
