CREATE MATERIALIZED VIEW mv_call_parts_rollup
ENGINE = AggregatingMergeTree()
ORDER BY project_id
POPULATE
AS
SELECT
    project_id,
    maxState( (length(id) != 36 OR substring(id, 15, 1) != '7') ) AS has_non_uuidv7
FROM call_parts
GROUP BY project_id