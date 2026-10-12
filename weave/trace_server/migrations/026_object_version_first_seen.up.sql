-- Track the first created_at per (project_id, object_id, digest) using
-- AggregatingMergeTree with minState.  This survives ReplacingMergeTree
-- merges on the source object_versions table, giving a stable anchor for
-- version_index ordering even when the same digest is re-published.

CREATE TABLE IF NOT EXISTS object_version_first_seen (
    project_id String,
    object_id String,
    digest String,
    first_created_at SimpleAggregateFunction(min, DateTime64(3))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, object_id, digest);

CREATE MATERIALIZED VIEW IF NOT EXISTS object_version_first_seen_view
TO object_version_first_seen AS
SELECT
    project_id,
    object_id,
    digest,
    minSimpleState(created_at) AS first_created_at
FROM object_versions
GROUP BY project_id, object_id, digest;

-- Backfill: seed the target table with min(created_at) from all existing rows.
-- Without this, re-publishing a pre-MV object would use the new created_at
-- (the MV only sees inserts after it's created, missing the original timestamp).
-- AggregatingMergeTree will merge this backfill with future MV inserts via min().
INSERT INTO object_version_first_seen
SELECT project_id, object_id, digest,
    minSimpleState(created_at) AS first_created_at
FROM object_versions
GROUP BY project_id, object_id, digest;
