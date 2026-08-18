-- Source of truth and full audit history for conversation tags. Rows are append-only.
CREATE TABLE IF NOT EXISTS conversation_tags
(
    project_id      String,
    conversation_id String,

    -- the turn's trace_id
    trace_id        String,

    -- the literal tag value, e.g. 'user-frustration'
    tag             String,

    -- Removal or re-add rows for a (conversation_id, trace_id, tag) must preserve trace_ended_at.
    trace_ended_at  DateTime64(6),

    -- The source responsible for this tag. Either an LLM judge or human.
    source          Enum8('judge' = 1, 'human' = 2),

    -- When source=judge, this is the version of the judge.
    judge_version   LowCardinality(String),

    -- When source=human, this is the id of the user.
    wb_user_id      String,

    -- The reasoning behind the tag being applied.
    rationale       String DEFAULT '' CODEC(ZSTD(3)),

    -- 1 = this row records the tag being removed
    --
    -- deleted_at in this case will be the same as inserted_at,
    -- so we don't need a second timestamp. Uint8 is simpler in
    -- some ways (no default value of 1970-01-01) and will allow
    -- us to use a ReplaceingMergeTree in the MV if needed.
    is_removed      UInt8 DEFAULT 0,

    -- If customers need to set a custom TTL
    expire_at DateTime DEFAULT '2100-01-01 00:00:00',

    -- When this record was inserted
    inserted_at     DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(trace_ended_at)
ORDER BY (project_id, conversation_id, trace_id, tag)
TTL expire_at DELETE;

-- Tag-centric copy for querying recent conversations with a given tag.
CREATE TABLE IF NOT EXISTS conversation_tags_by_tag
(
    project_id      String,
    conversation_id String,
    trace_id        String,
    tag             String,
    trace_ended_at  DateTime64(6),
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
ORDER BY (project_id, tag, trace_ended_at, conversation_id, trace_id)
TTL expire_at DELETE;

CREATE MATERIALIZED VIEW IF NOT EXISTS conversation_tags_by_tag_mv
TO conversation_tags_by_tag AS
SELECT
    project_id,
    tag,
    trace_ended_at,
    conversation_id,
    trace_id,
    source,
    judge_version,
    wb_user_id,
    rationale,
    is_removed,
    expire_at,
    inserted_at
FROM conversation_tags;
