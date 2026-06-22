-- Stable per-span size stats for usage billing, mirroring calls_complete_stats.
-- Bills raw_span_dump (the full serialized span) once: every other span column
-- is a subset of it, so summing them would multi-count the same bytes.
-- Forward-only: existing spans are not backfilled, so billing starts from the
-- migration date. Partitioned and keyed by (project_id, started_at, span_id)
-- to match the raw spans table, so the daily billing scan hits one month
-- partition and prunes on started_at within it.

CREATE TABLE IF NOT EXISTS spans_stats
(
    project_id String,
    started_at DateTime64(6),
    span_id String,
    size_bytes SimpleAggregateFunction(any, UInt64),
    created_at SimpleAggregateFunction(min, DateTime64(3))
) ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, started_at, span_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS spans_stats_view
TO spans_stats
AS
SELECT
    spans.project_id,
    spans.started_at,
    spans.span_id,
    anySimpleState(length(spans.raw_span_dump)) as size_bytes,
    minSimpleState(spans.created_at) as created_at
FROM spans
GROUP BY
    spans.project_id,
    spans.started_at,
    spans.span_id;
