CREATE TABLE IF NOT EXISTS conversation_tag_assignments
(
    project_id      String,
    conversation_id String,
    trace_id        String,
    tag_id          UUID,
    trace_ended_at  DateTime64(6),
    agent_id        String DEFAULT '',
    agent_name      String DEFAULT '',
    agent_version   String DEFAULT '',
    source          Enum8('judge' = 1, 'human' = 2),
    judge_version   LowCardinality(String),
    wb_user_id      String,
    rationale       String DEFAULT '' CODEC(ZSTD(3)),
    is_removed      UInt8 DEFAULT 0,
    expire_at       DateTime DEFAULT '2100-01-01 00:00:00',
    inserted_at     DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(trace_ended_at)
ORDER BY (project_id, conversation_id, trace_id, tag_id)
TTL expire_at DELETE;

CREATE TABLE IF NOT EXISTS conversation_tag_assignments_by_tag
(
    project_id      String,
    conversation_id String,
    trace_id        String,
    tag_id          UUID,
    trace_ended_at  DateTime64(6),
    agent_id        String DEFAULT '',
    agent_name      String DEFAULT '',
    agent_version   String DEFAULT '',
    source          Enum8('judge' = 1, 'human' = 2),
    judge_version   LowCardinality(String),
    wb_user_id      String,
    rationale       String DEFAULT '' CODEC(ZSTD(3)),
    is_removed      UInt8 DEFAULT 0,
    expire_at       DateTime DEFAULT '2100-01-01 00:00:00',
    inserted_at     DateTime64(6) DEFAULT now64(6)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(trace_ended_at)
ORDER BY (project_id, tag_id, trace_ended_at, conversation_id, trace_id)
TTL expire_at DELETE;

CREATE MATERIALIZED VIEW IF NOT EXISTS conversation_tag_assignments_by_tag_mv
TO conversation_tag_assignments_by_tag AS
SELECT
    project_id,
    conversation_id,
    trace_id,
    tag_id,
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
FROM conversation_tag_assignments;
