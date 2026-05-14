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
--
-- Implementation notes (alias-shadow avoidance):
--   1. WHERE uses `ov.deleted_at IS NULL` against the qualified column.
--      Writing `deleted_at = toDateTime64(0, 3)` here would let CH's
--      analyzer shadow-resolve `deleted_at` to the SELECT-projection
--      constant `toDateTime64(0, 3) AS deleted_at` — making the predicate
--      `toDateTime64(0,3) = toDateTime64(0,3)`, always TRUE, which would
--      include tombstoned rows in the backfill.
--   2. `argMax(ov.digest, ov.created_at)` uses qualified column names so
--      the second argument binds to `object_versions.created_at`, not the
--      SELECT-projection constant `toDateTime64('1970-01-01 ...', 3) AS
--      created_at`. Without qualification CH would tie on the constant
--      for every row and break ties by storage order (lex-smallest
--      digest wins), producing the wrong "latest" digest.
INSERT INTO aliases (project_id, object_id, alias, digest, wb_user_id, created_at, deleted_at)
SELECT
    ov.project_id,
    ov.object_id,
    'latest',
    argMax(ov.digest, ov.created_at),
    '__weave_backfill_031__',
    toDateTime64('1970-01-01 00:00:00.001', 3),
    toDateTime64(0, 3)
FROM object_versions AS ov
WHERE ov.deleted_at IS NULL
GROUP BY ov.project_id, ov.object_id;
