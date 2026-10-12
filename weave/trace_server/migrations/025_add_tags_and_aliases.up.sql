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
    deleted_at DateTime64(3) DEFAULT toDateTime64(0, 3)
) ENGINE = ReplacingMergeTree(created_at)
-- Includes digest: "reviewed" on v0 and "reviewed" on v1 coexist as separate rows.
ORDER BY (project_id, object_id, digest, tag)
SETTINGS
    min_bytes_for_wide_part=0,
    enable_block_number_column=1,
    enable_block_offset_column=1;

CREATE TABLE IF NOT EXISTS aliases (
    project_id String,
    object_id String,
    alias String,
    digest String,
    wb_user_id String DEFAULT '',
    created_at DateTime64(3) DEFAULT now64(3),
    deleted_at DateTime64(3) DEFAULT toDateTime64(0, 3)
) ENGINE = ReplacingMergeTree(created_at)
-- Excludes digest: setting "prod" on v1 then v2 collapses to one row after merge.
ORDER BY (project_id, object_id, alias)
SETTINGS
    min_bytes_for_wide_part=0,
    enable_block_number_column=1,
    enable_block_offset_column=1;
