-- Tags: per-version labels. Same tag on different digests = separate rows.
-- Aliases: per-object named pointers. One alias points to one digest at a time.
-- Both use ReplacingMergeTree soft-delete: INSERT with deleted_at=now() to remove.

CREATE TABLE IF NOT EXISTS tags (
    project_id String,
    object_id String,
    digest String,
    tag String,
    wb_user_id String DEFAULT '',
    created_at DateTime64(3) DEFAULT now64(3),
    deleted_at Nullable(DateTime64(3)) DEFAULT NULL
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (project_id, object_id, digest, tag);

CREATE TABLE IF NOT EXISTS aliases (
    project_id String,
    object_id String,
    alias String,
    digest String,
    wb_user_id String DEFAULT '',
    created_at DateTime64(3) DEFAULT now64(3),
    deleted_at Nullable(DateTime64(3)) DEFAULT NULL
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (project_id, object_id, alias);
