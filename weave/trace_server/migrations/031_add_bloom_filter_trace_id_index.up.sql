-- Migration 031: Add bloom filter index on ifNull(trace_id, '') to
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
--
-- Lazy backfill: we deliberately skip MATERIALIZE INDEX. On a large
-- calls_merged that would block the migration on full-table reindexing
-- and compete with ingest. New parts get the index from the moment this
-- migration applies, and existing parts gain it as parts are naturally
-- re-merged. Operators who want immediate coverage can run
-- `ALTER TABLE calls_merged MATERIALIZE INDEX idx_trace_id_bloom`
-- out-of-band.
ALTER TABLE calls_merged
    ADD INDEX IF NOT EXISTS idx_trace_id_bloom
        ifNull(trace_id, '') TYPE bloom_filter(0.01) GRANULARITY 1;
