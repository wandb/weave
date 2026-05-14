-- Backfill explicit "latest" alias rows for objects created before the
-- explicit alias write was added (see PR for WB-32435). Rows are inserted
-- with an epoch created_at so any subsequent real obj_create alias write
-- wins on ReplacingMergeTree(created_at) merge.
--
-- Backfill rows are tagged with wb_user_id = '__weave_backfill_031__' so
-- the down migration can identify them unambiguously. Real obj_create
-- alias writes never produce this value.
--
-- The backfill is not required for correctness — the API's hybrid
-- is_latest projection falls back to a computed window-function rank
-- over object_versions when no live alias row exists — but it puts all
-- objects on the same code path (alias-based) by default, which is
-- easier to reason about for ad-hoc queries and dashboards.
INSERT INTO aliases (project_id, object_id, alias, digest, wb_user_id, created_at, deleted_at)
SELECT
    project_id,
    object_id,
    'latest' AS alias,
    argMax(digest, created_at) AS digest,
    '__weave_backfill_031__' AS wb_user_id,
    toDateTime64('1970-01-01 00:00:00.001', 3) AS created_at,
    toDateTime64(0, 3) AS deleted_at
FROM object_versions
WHERE deleted_at = toDateTime64(0, 3)
GROUP BY project_id, object_id;
