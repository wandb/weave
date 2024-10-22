CREATE TABLE actions_parts (
    project_id String,
    call_id String,
    id String,
    rule_matched Nullable(String),
    effect Nullable(String),
    created_at Nullable(DateTime64(3)),
    finished_at Nullable(DateTime64(3)),
    failed_at Nullable(DateTime64(3))
    -- INDEX idx_created_at created_at TYPE minmax,
    -- INDEX idx_finished_at finished_at TYPE minmax,
    -- INDEX idx_failed_at failed_at TYPE minmax
) Engine = MergeTree()
ORDER BY (project_id, call_id, id);
-- Add TTL?

CREATE TABLE actions_merged (
    project_id String,
    call_id String,
    id String,
    rule_matched SimpleAggregateFunction(any, Nullable(String)),
    effect SimpleAggregateFunction(any, Nullable(String)),
    created_at SimpleAggregateFunction(max, Nullable(DateTime64(3))),
    finished_at SimpleAggregateFunction(max, Nullable(DateTime64(3))),
    failed_at SimpleAggregateFunction(max, Nullable(DateTime64(3))),
    INDEX idx_created_at created_at TYPE minmax,
    INDEX idx_finished_at finished_at TYPE minmax,
    INDEX idx_failed_at failed_at TYPE minmax
) Engine = AggregatingMergeTree()
ORDER BY (project_id, call_id, id);
-- Add TTL?

CREATE MATERIALIZED VIEW actions_view
TO actions_merged
AS
SELECT
    project_id,
    call_id,
    id,
    anySimpleState(rule_matched) AS rule_matched,
    anySimpleState(effect) AS effect,
    maxSimpleState(created_at) AS created_at,
    maxSimpleState(finished_at) AS finished_at,
    maxSimpleState(failed_at) AS failed_at
FROM actions_parts
GROUP BY project_id, call_id, id;
