ALTER TABLE calls_merged ADD INDEX minmax_started_at (started_at) TYPE minmax GRANULARITY 1;
ALTER TABLE calls_merged ADD INDEX minmax_ended_at (ended_at) TYPE minmax GRANULARITY 1;