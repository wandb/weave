-- Source of truth and full audit history for conversation tags. Rows are append-only.
CREATE TABLE IF NOT EXISTS conversation_tags
(
    project_id      String,
    conversation_id String,
    trace_id        String,
    tag             LowCardinality(String),

    source          Enum8('judge' = 1, 'human' = 2),
    source_version  LowCardinality(String),
    wb_user_id      String,

    -- Removal and re-add rows for a (trace_id, tag) must preserve trace_ended_at.
    trace_ended_at  DateTime64(6),
    rationale       String DEFAULT '' CODEC(ZSTD(3)),
    inserted_at     DateTime64(6) DEFAULT now64(6),
    is_removed      UInt8 DEFAULT 0
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(trace_ended_at)
ORDER BY (project_id, conversation_id, trace_id, tag);

-- Tag-centric copy for querying recent conversations with a given tag.
CREATE TABLE IF NOT EXISTS conversation_tags_by_tag
(
    project_id      String,
    tag             LowCardinality(String),
    trace_ended_at  DateTime64(6),
    conversation_id String,
    trace_id        String,
    source          Enum8('judge' = 1, 'human' = 2),
    source_version  LowCardinality(String),
    wb_user_id      String,
    rationale       String DEFAULT '' CODEC(ZSTD(3)),
    inserted_at     DateTime64(6) DEFAULT now64(6),
    is_removed      UInt8 DEFAULT 0
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(trace_ended_at)
ORDER BY (project_id, tag, trace_ended_at, conversation_id, trace_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS conversation_tags_by_tag_mv
TO conversation_tags_by_tag AS
SELECT
    project_id,
    tag,
    trace_ended_at,
    conversation_id,
    trace_id,
    source,
    source_version,
    wb_user_id,
    rationale,
    inserted_at,
    is_removed
FROM conversation_tags;
