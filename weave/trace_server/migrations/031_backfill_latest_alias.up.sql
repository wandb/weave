-- Backfill explicit "latest" alias rows for objects created before the
-- explicit alias write was added (see PR for WB-32435). Rows are inserted
-- with an epoch created_at so any subsequent real obj_create alias write
-- wins on ReplacingMergeTree(created_at) merge.
--
-- Backcompat / consistency notes:
--  * Any external consumer that read objects.is_latest directly (ad-hoc CH
--    queries, dashboards) is now divergent from the API: the API derives
--    is_latest from this aliases table, not from object_versions ordering.
--  * On a multi-replica cluster, this INSERT applies once but reads can
--    hit a replica before the row is fully merged into the RMT — for the
--    "latest" case this is harmless because the prior computed-at-read
--    behavior already returned the same row, but be aware.
INSERT INTO aliases (project_id, object_id, alias, digest, wb_user_id, created_at, deleted_at)
SELECT
    project_id,
    object_id,
    'latest' AS alias,
    argMax(digest, created_at) AS digest,
    '' AS wb_user_id,
    toDateTime64('1970-01-01 00:00:00.001', 3) AS created_at,
    toDateTime64(0, 3) AS deleted_at
FROM object_versions
WHERE deleted_at = toDateTime64(0, 3)
GROUP BY project_id, object_id;
