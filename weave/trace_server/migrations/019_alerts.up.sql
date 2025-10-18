CREATE TABLE IF NOT EXISTS alert_metrics (
   project_id String,
   id String,
   wb_user_id String,
   call_id String,
   alert_ids Array(String),
   created_at Datetime(3),
   created_at_inv DateTime(3) MATERIALIZED toDateTime64(2147483647 - toUnixTimestamp64Milli(created_at), 3),
   metric_key String,
   metric_value Float64,
   metric_type String,

   INDEX idx_alert_ids (alert_ids) TYPE bloom_filter(0.01) GRANULARITY 1
) ENGINE = MergeTree
ORDER BY (project_id, metric_key, created_at_inv, id);

-- Aggregate hourly, used to serve week old data
CREATE TABLE IF NOT EXISTS alert_metrics_history (
	project_id String, 
  metric_key String,
  bucket_start DateTime64(3),

  wb_user_ids AggregateFunction(groupUniqArray, Array(String)),
	alert_ids AggregateFunction(groupUniqArray, Array(String)),
	min_created_at SimpleAggregateFunction(min, Datetime(3)),
	max_created_at SimpleAggregateFunction(max, Datetime(3)),
  metric_sum   SimpleAggregateFunction(sum, Float64),
	metric_count SimpleAggregateFunction(sum, UInt64)
)
ENGINE = AggregatingMergeTree
ORDER BY (project_id, metric_key, bucket_start)
TTL toDateTime(bucket_start) + INTERVAL 3 MONTH;

CREATE MATERIALIZED VIEW IF NOT EXISTS alert_metrics_history_view
TO alert_metrics_history AS
SELECT
  project_id,
  metric_key,
  bucket_start,
  groupUniqArray(wb_user_id)              AS wb_user_ids,
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