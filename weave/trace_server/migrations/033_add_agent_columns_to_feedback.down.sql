ALTER TABLE feedback
    DROP INDEX IF EXISTS idx_span_agent_name,
    DROP INDEX IF EXISTS idx_span_agent_version;

ALTER TABLE feedback
    DROP COLUMN IF EXISTS span_agent_name,
    DROP COLUMN IF EXISTS span_agent_version,
    DROP COLUMN IF EXISTS span_status_code;
