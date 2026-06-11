-- Dataset row provenance: links dataset rows to their source calls/spans.
-- Insert-only versioning via ReplacingMergeTree(updated_at); reads collapse
-- duplicate versions with GROUP BY + argMax (never FINAL).
CREATE TABLE IF NOT EXISTS dataset_sources (
    id String,
    project_id String,
    dataset_object_id String,
    row_digest String,
    source_kind Enum8('call' = 1, 'span' = 2, 'conversation' = 3),
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
-- A span's identity is (trace_id, span_id), so source_trace_id is part of the
-- logical key (last, since reads filter by the source_id bloom, never trace_id).
-- For calls it is redundant (call_id is globally unique) but harmless, keeping
-- one uniform key across both source kinds.
ORDER BY (project_id, dataset_object_id, row_digest, source_kind, source_id, source_trace_id);
