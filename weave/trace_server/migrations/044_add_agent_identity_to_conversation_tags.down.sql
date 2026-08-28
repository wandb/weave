DROP VIEW IF EXISTS conversation_tags_by_tag_mv;

ALTER TABLE conversation_tags_by_tag
    DROP COLUMN IF EXISTS agent_version,
    DROP COLUMN IF EXISTS agent_id;

ALTER TABLE conversation_tags
    DROP COLUMN IF EXISTS agent_version,
    DROP COLUMN IF EXISTS agent_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS conversation_tags_by_tag_mv
TO conversation_tags_by_tag AS
SELECT
    project_id,
    conversation_id,
    trace_id,
    tag,
    trace_ended_at,
    agent_name,
    source,
    judge_version,
    wb_user_id,
    rationale,
    is_removed,
    expire_at,
    inserted_at
FROM conversation_tags;
