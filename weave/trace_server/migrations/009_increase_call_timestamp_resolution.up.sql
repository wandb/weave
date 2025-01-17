-- Increase the resolution of the call timestamps to 6 decimal places from 3
ALTER TABLE call_parts MODIFY COLUMN started_at Nullable(DateTime64(6));
ALTER TABLE call_parts MODIFY COLUMN ended_at Nullable(DateTime64(6));

ALTER TABLE calls_merged MODIFY COLUMN started_at SimpleAggregateFunction(any, Nullable(DateTime64(6)));
ALTER TABLE calls_merged MODIFY COLUMN ended_at SimpleAggregateFunction(any, Nullable(DateTime64(6)));
