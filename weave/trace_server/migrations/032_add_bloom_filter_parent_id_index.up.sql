-- Migration 032: Add bloom filter index on ifNull(parent_id, '') to
-- accelerate parent-scoped lookups in calls_merged.
--
-- The eval-drawer query (`/eval_results/query`) filters by
-- `parent_id IN (eval_root_ids)` to find every predict_and_score child of
-- an eval root. calls_merged is ordered by `(project_id, id)` with no
-- skip-index on parent_id, so this currently scans every granule in the
-- project's partition (multi-million-row hot projects → multi-second
-- queries, p95 ~10s, p99 ~60s in prod).
--
-- The column is `SimpleAggregateFunction(any, Nullable(String))` because
-- pre-merge rows in calls_merged can transiently be NULL until the
-- AggregatingMergeTree merges parts. A bloom filter built directly on a
-- Nullable column does not get pruned by `WHERE parent_id = 'x'` due to
-- Nullable-equality semantics. Wrapping the index expression in
-- `ifNull(parent_id, '')` (and matching the predicate in the query layer
-- character-for-character) makes the comparison non-nullable on both
-- sides so the index actually fires.
--
-- Pairs with the candidate-ids CTE rewrite in eval_results_query_builder
-- (the existing query's `parent_id IN (...) OR parent_id IS NULL` shape
-- prevents the index from firing on its own; the CTE isolates the tight
-- IN-arm so the bloom can prune granules).
ALTER TABLE calls_merged
    ADD INDEX IF NOT EXISTS idx_parent_id_bloom
        ifNull(parent_id, '') TYPE bloom_filter(0.01) GRANULARITY 1;

-- Kick off background materialization for existing parts. mutations_sync
-- defaults to 0, so this returns immediately and ClickHouse runs the
-- mutation asynchronously instead of blocking the migration on a full-
-- table reindex.
ALTER TABLE calls_merged
    MATERIALIZE INDEX idx_parent_id_bloom;
