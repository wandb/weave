-- Migration 032: Add bloom filter index on ifNull(trace_id, '') to
-- accelerate trace-scoped lookups (e.g. fetching every call in a trace).
--
-- trace_id values are random (UUIDs / OTel trace IDs), so the table's
-- (project_id, id) primary key gives no locality on trace_id and queries
-- like `WHERE trace_id = 'x'` fall back to scanning every granule.
--
-- The column is `SimpleAggregateFunction(any, Nullable(String))` because
-- pre-merge rows in calls_merged can transiently be NULL until the
-- AggregatingMergeTree merges parts. A bloom filter built directly on a
-- Nullable column does not get pruned by `WHERE trace_id = 'x'` due to
-- Nullable-equality semantics. Wrapping the index expression in
-- `ifNull(trace_id, '')` (and matching the predicate in the query layer
-- character-for-character) makes the comparison non-nullable on both
-- sides so the index actually fires.
-- alter_sync = 1 forces the metadata change to land on the local replica
-- before the next statement runs, so the MATERIALIZE below is guaranteed
-- to see the new index (matches the convention in migrations 012 and 028).
ALTER TABLE calls_merged
    ADD INDEX IF NOT EXISTS idx_trace_id_bloom
        ifNull(trace_id, '') TYPE bloom_filter(0.01) GRANULARITY 1
    SETTINGS alter_sync = 1;

-- Kick off background materialization for existing parts. mutations_sync
-- defaults to 0, so this returns immediately and ClickHouse runs the
-- mutation asynchronously instead of blocking the migration on a full-
-- table reindex.
ALTER TABLE calls_merged
    MATERIALIZE INDEX idx_trace_id_bloom;
