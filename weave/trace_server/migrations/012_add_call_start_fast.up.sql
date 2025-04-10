CREATE TABLE IF NOT EXISTS call_start_fast (
  id String,
  project_id String,
  started_at Datetime(6),
  
  op_name String,
  trace_id String,
  
  parent_id String DEFAULT ''
) ENGINE = MergeTree
ORDER BY (project_id, op_name, trace_id, parent_id, started_at, id);

CREATE MATERIALIZED VIEW IF NOT EXISTS call_start_fast_view TO call_start_fast AS
SELECT 
   project_id,
   id,
   started_at,
   op_name,
   trace_id,
   COALESCE(parent_id, '') as parent_id
FROM call_parts
WHERE started_at is not NULL
ORDER BY (project_id, op_name, trace_id, parent_id, started_at, id);

--------------- [backfill] -----------------
INSERT INTO call_start_fast (
    id,
    project_id,
    started_at,
    op_name,
    trace_id,
    parent_id
) SELECT
    id,
    project_id,
    started_at,
    op_name,
    trace_id,
    COALESCE(parent_id, '') as parent_id
FROM call_parts
WHERE started_at is not NULL
AND created_at >= (
    SELECT COALESCE(
        -- Get the oldest started_at in call_start_fast, or oldest created from call_parts
        (SELECT min(started_at) FROM call_parts WHERE started_at > (SELECT max(started_at) FROM call_start_fast)),
        (SELECT min(created_at) FROM call_parts)
    )
);
