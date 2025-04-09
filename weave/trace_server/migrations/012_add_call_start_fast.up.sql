DROP TABLE IF EXISTS call_start_fast;
CREATE TABLE call_start_fast (
  id String,
  project_id String,
  started_at Datetime(6),
  
  op_name String,
  trace_id String,
  
  parent_id String DEFAULT ''
) ENGINE = MergeTree
ORDER BY (project_id, op_name, trace_id, parent_id, id, started_at);

DROP VIEW IF EXISTS call_start_fast_view;
CREATE MATERIALIZED VIEW call_start_fast_view TO call_start_fast AS
SELECT 
   project_id,
   id,
   started_at,
   op_name,
   trace_id,
   COALESCE(parent_id, '') as parent_id
FROM call_parts
WHERE started_at is not NULL
ORDER BY (project_id, op_name, trace_id, parent_id, id, started_at);
