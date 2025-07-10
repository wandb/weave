CREATE TABLE calls_complete (
	id String,
	project_id String,
	
	created_at DateTime64(6) DEFAULT now64(6),
	started_at DateTime64(6),
	ended_at Nullable(DateTime64(6)),
	deleted_at Nullable(DateTime64(6)),
	started_at_inverse Int64
        MATERIALIZED (-toUnixTimestamp64Micro(started_at)),
	
	-- indexable fields
	trace_id String,
	parent_id Nullable(String),
	op_name String,
	
	-- dump fields
	inputs_dump String,
	attributes_dump String,
	output_dump Nullable(String),
	summary_dump Nullable(String),
	input_refs Array(String),
	output_refs Array(String),
	
	wb_user_id String,
	wb_run_id Nullable(String),
	turn_id Nullable(String),
	thread_id Nullable(String),
	wb_run_step Nullable(UInt64),
	
	exception Nullable(String),
	display_name Nullable(String),
	
	-- TODO: tune bloom filters
  INDEX idx_trace_id  trace_id  TYPE bloom_filter(0.001) GRANULARITY 1,
  INDEX idx_op_name   op_name   TYPE bloom_filter(0.001) GRANULARITY 1,
  INDEX idx_parent_id parent_id TYPE bloom_filter(0.001) GRANULARITY 1,
  
  INDEX idx_started_at started_at TYPE minmax GRANULARITY 1,
  -- This does not appear to work...
  INDEX idx_attributes_dump attributes_dump TYPE bloom_filter(0.001) GRANULARITY 1
	
) ENGINE = MergeTree
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, started_at_inverse, id)
SETTINGS min_bytes_for_wide_part=0 -- forces all data to be wide

