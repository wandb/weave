-- Source of truth and full audit history for trace tags. Rows are append-only.
CREATE TABLE IF NOT EXISTS trace_tags
(
    project_id      String,
    conversation_id String,
    trace_id        String,
    tag             LowCardinality(String),

    source          Enum8('judge' = 1, 'human' = 2),
    source_version  LowCardinality(String),
    wb_user_id      String,

    -- Removal and re-add rows for a (trace_id, tag) must preserve trace_ts.
    trace_ts        DateTime64(3),
    rationale       String DEFAULT '' CODEC(ZSTD(3)),
    inserted_at     DateTime64(6),
    is_removed      UInt8 DEFAULT 0
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(trace_ts)
ORDER BY (project_id, conversation_id, trace_id, tag);

-- Tag-centric copy for querying recent traces with a given tag.
CREATE TABLE IF NOT EXISTS trace_tags_by_tag
(
    project_id      String,
    tag             LowCardinality(String),
    trace_ts        DateTime64(3),
    conversation_id String,
    trace_id        String,
    source          Enum8('judge' = 1, 'human' = 2),
    source_version  LowCardinality(String),
    wb_user_id      String,
    rationale       String DEFAULT '' CODEC(ZSTD(3)),
    inserted_at     DateTime64(6),
    is_removed      UInt8 DEFAULT 0
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(trace_ts)
ORDER BY (project_id, tag, trace_ts, conversation_id, trace_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS trace_tags_by_tag_mv
TO trace_tags_by_tag AS
SELECT
    project_id,
    tag,
    trace_ts,
    conversation_id,
    trace_id,
    source,
    source_version,
    wb_user_id,
    rationale,
    inserted_at,
    is_removed
FROM trace_tags;

-- Current trace-centric state, with the latest audit row winning.
CREATE VIEW IF NOT EXISTS trace_tags_current AS
SELECT
    project_id,
    conversation_id,
    trace_id,
    tag,
    argMax(source, trace_tags.inserted_at) AS source,
    argMax(trace_ts, trace_tags.inserted_at) AS trace_ts,
    argMax(source_version, trace_tags.inserted_at) AS source_version,
    argMax(wb_user_id, trace_tags.inserted_at) AS wb_user_id,
    argMax(rationale, trace_tags.inserted_at) AS rationale,
    max(trace_tags.inserted_at) AS inserted_at
FROM trace_tags
GROUP BY project_id, conversation_id, trace_id, tag
HAVING argMax(is_removed, trace_tags.inserted_at) = 0;

-- Current tag-centric state, ordered efficiently by the backing table's key.
CREATE VIEW IF NOT EXISTS trace_tags_by_tag_current AS
SELECT
    project_id,
    tag,
    trace_ts,
    conversation_id,
    trace_id,
    argMax(source, trace_tags_by_tag.inserted_at) AS source,
    argMax(source_version, trace_tags_by_tag.inserted_at) AS source_version,
    argMax(wb_user_id, trace_tags_by_tag.inserted_at) AS wb_user_id,
    argMax(rationale, trace_tags_by_tag.inserted_at) AS rationale,
    max(trace_tags_by_tag.inserted_at) AS inserted_at
FROM trace_tags_by_tag
GROUP BY project_id, tag, trace_ts, conversation_id, trace_id
HAVING argMax(is_removed, trace_tags_by_tag.inserted_at) = 0;
