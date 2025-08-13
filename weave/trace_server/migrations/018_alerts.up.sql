-- 4 tables:
-- 1. Define alert metadata, threshold, description, trigger event (webhook)
-- 2. Event log of actually triggered events, when did the alert fire 
-- 3. All calculated alert data
-- 4. All calculated alert data history

-- CREATE TABLE IF NOT EXISTS alerts (
--    project_id String,
--    id String,
--    version UInt64,
--    created_at Datetime(3),
--    spec JSON,
-- ) ENGINE = MergeTree
-- ORDER BY (project_id, id, version, created_at)

CREATE TABLE IF NOT EXISTS alert_events (
   project_id String,
   id String,
   alert_ref String, -- weave_ref to objects table
   alert_id String, -- digest of alert_ref
   created_at Datetime(3),
   level Enum('log', 'ok', 'warn', 'alert')
) ENGINE = ReplacingMergeTree
ORDER BY (project_id, alert_id, id, created_at);
   
CREATE TABLE IF NOT EXISTS alert_metrics (
   project_id String,
   id String, -- necessary?
   alert_ids Array(String), -- multiple alerts can have the same metric
   created_at Datetime(3),
   metric_key String,
   metric_value Double, -- can this ever not be float?
   
   -- TODO: decide between primary key or skip index for metric_key, alert_ids
   --INDEX idx_metric_key (metric_key) TYPE set(10) GRANULARITY 1,
   INDEX idx_alert_ids (alert_ids) TYPE bloom_filter(0.01) GRANULARITY 1
) ENGINE = MergeTree()
ORDER BY (project_id, metric_key, created_at, id);
   
-- Aggregate hourly, used to serve week old data
CREATE TABLE IF NOT EXISTS alert_metrics_history (
	project_id String, 
    metric_key String,
    bucket_start DateTime64(3),
    
	alert_ids AggregateFunction(groupUniqArray, Array(String)),
	min_created_at SimpleAggregateFunction(min, Datetime(3)),
	max_created_at SimpleAggregateFunction(max, Datetime(3)),
    metric_sum   SimpleAggregateFunction(sum, Float64),
	metric_count SimpleAggregateFunction(sum, UInt64)
)
ENGINE = AggregatingMergeTree
ORDER BY (project_id, metric_key, bucket_start)
TTL bucket_start + INTERVAL 3 MONTH;

CREATE MATERIALIZED VIEW IF NOT EXISTS alert_metrics_history_view
TO alert_metrics_history AS
SELECT
  project_id,
  metric_key,
  bucket_start,
  groupUniqArrayState(alert_ids)          AS alert_ids,
  min(created_at)                         AS min_created_at,
  max(created_at)                         AS max_created_at,
  sum(metric_value)                       AS metric_sum,
  count()                                 AS metric_count
FROM alert_metrics
GROUP BY
  project_id,
  metric_key,
  toStartOfHour(created_at) AS bucket_start;
