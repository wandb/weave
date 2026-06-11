-- Dataset row provenance: links dataset rows to their source calls/spans.
--
-- TODO(membership_pattern): this is the second instance of the membership
-- pattern (see annotation_queue_items, migration 023). If you are about to
-- add a THIRD sibling table for this pattern, STOP and design a shared
-- contract first. Shared invariants: weave/trace_server/docs/membership_pattern.md
CREATE TABLE IF NOT EXISTS dataset_sources (
    id String,
    project_id String,
    dataset_object_id String,
    row_digest String,
    source_kind Enum8('call' = 1, 'span' = 2),
    source_id String,
    source_trace_id String,
    source_started_at DateTime64(6),
    source_display_name String,
    link_metadata String DEFAULT '',
    added_by Nullable(String),
    created_at DateTime64(3) DEFAULT now64(3),
    -- updated_at is the ReplacingMergeTree version column AND the read-side
    -- argMax tiebreaker. Link ids are deterministic (same logical key -> same
    -- id), so id can NOT break ties between versions of the same link —
    -- updated_at must. Microsecond precision makes sequential operations
    -- (e.g. delete then relink) always distinct; only truly concurrent writes
    -- can tie, where either outcome is acceptable.
    updated_at DateTime64(6) DEFAULT now64(6),
    deleted_at Nullable(DateTime64(3)),
    INDEX idx_source_id source_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_source_trace_id source_trace_id TYPE bloom_filter GRANULARITY 1
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (project_id, dataset_object_id, row_digest, source_kind, source_id);
