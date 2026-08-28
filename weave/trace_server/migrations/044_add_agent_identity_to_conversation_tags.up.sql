ALTER TABLE conversation_tags
    ADD COLUMN IF NOT EXISTS agent_id      String DEFAULT '' AFTER trace_ended_at,
    ADD COLUMN IF NOT EXISTS agent_version String DEFAULT '' AFTER agent_name;

ALTER TABLE conversation_tags_by_tag
    ADD COLUMN IF NOT EXISTS agent_id      String DEFAULT '' AFTER trace_ended_at,
    ADD COLUMN IF NOT EXISTS agent_version String DEFAULT '' AFTER agent_name;

DROP VIEW IF EXISTS conversation_tags_by_tag_mv;

CREATE MATERIALIZED VIEW IF NOT EXISTS conversation_tags_by_tag_mv
TO conversation_tags_by_tag AS
SELECT
    project_id,
    conversation_id,
    trace_id,
    tag,
    trace_ended_at,
    agent_id,
    agent_name,
    agent_version,
    source,
    judge_version,
    wb_user_id,
    rationale,
    is_removed,
    expire_at,
    inserted_at
FROM conversation_tags;
