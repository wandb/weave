-- Dataset row provenance: links dataset rows to the calls / agent spans /
-- conversations that produced them (queryable both directions).
-- Insert-only versioning via ReplacingMergeTree(updated_at). Reads collapse
-- duplicate versions with GROUP BY + argMax (never FINAL).
CREATE TABLE IF NOT EXISTS dataset_sources (
    id String,
    project_id String,
    dataset_object_id String,
    row_digest String,
    source_kind Enum8('call' = 1, 'span' = 2, 'conversation' = 3),
    source_id String,
    source_trace_id String,
    -- source_started_at / source_display_name are denormalized SNAPSHOTS of the
    -- source captured at link time, NOT live joins. This table owns no SQL
    -- against the calls/spans tables, and a conversation has no source row to
    -- join at all. Provenance is also a frozen claim about write-time. Contract:
    -- these reflect the source as of when it was linked — a later rename of the
    -- call/span is intentionally NOT reflected here.
    source_started_at DateTime64(6),
    source_display_name String,
    link_metadata String DEFAULT '',
    -- added_by / deleted_at use sentinels ('' and the 1970 epoch) instead of
    -- Nullable -- cheaper in ClickHouse and lets us add skip indexes later. The
    -- app layer maps sentinel to/from None at the CH boundary (ch_sentinel_values).
    added_by String DEFAULT '',
    created_at DateTime64(3) DEFAULT now64(3),
    -- updated_at is the ReplacingMergeTree version column AND the read-side
    -- argMax tiebreaker. Link ids are deterministic (same logical key -> same
    -- id), so id can NOT break ties between versions of the same link —
    -- updated_at must. Microsecond precision makes sequential operations
    -- (e.g. delete then relink) always distinct. Only truly concurrent writes
    -- can tie, where either outcome is acceptable.
    updated_at DateTime64(6) DEFAULT now64(6),
    -- Sentinel epoch (1970) means "not deleted". A tombstone sets it to now().
    deleted_at DateTime64(3) DEFAULT toDateTime64(0, 3),
    INDEX idx_source_id source_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_source_trace_id source_trace_id TYPE bloom_filter(0.01) GRANULARITY 1
) ENGINE = ReplacingMergeTree(updated_at)
-- Monthly partitions on created_at (the link's write time) bound part sizes and
-- let retention drop whole months. A dataset's links can span months, which is
-- fine. Matches the agent spans table's monthly partitioning.
PARTITION BY toYYYYMM(created_at)
-- A span's identity is (trace_id, span_id), so source_trace_id is part of the
-- logical key (last, since reads filter by the source_id bloom, never trace_id).
-- It is redundant for calls (call_id is globally unique) and empty ('') for
-- conversations (a conversation spans traces, so conversation_id is sufficient
-- identity). Kept uniform across all three source kinds. The write layer
-- enforces these invariants (conversation -> '', call/span -> non-empty trace).
ORDER BY (project_id, dataset_object_id, row_digest, source_kind, source_id, source_trace_id)
-- min_bytes_for_wide_part=0 forces wide parts so the skip (bloom) indexes work
-- on the small parts produced by per-request inserts — skip indexes are ignored
-- on compact parts. Matches the agent `spans` table.
--
-- No TTL by design: provenance is a frozen record and must OUTLIVE the
-- calls/spans it references (those carry their own TTL), so a link that dangles
-- after its source expires is intended, not a leak.
SETTINGS min_bytes_for_wide_part = 0;
