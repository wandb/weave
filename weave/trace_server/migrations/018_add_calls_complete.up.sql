CREATE TABLE calls_final (
	id String,
	project_id String,
	
	started_at DateTime64(6),
	ended_at Nullable(DateTime64(6)),
	deleted_at Nullable(DateTime64(6)),
	reverse_timestamp Int64 MATERIALIZED (-toUnixTimestamp64Micro(started_at)),
	
	-- indexable fields
	trace_id String,
	parent_id Nullable(string),
	op_name String,
	
	-- dump fields
	inputs_dump String,
	attributes_dump String,
	output_dump Nullable(string),
	summary_dump Nullable(string),
	input_refs Array(String),
	output_refs Array(String),
	
	wb_user_id String,
	wb_run_id Nullable(string),
	turn_id Nullable(string),
	thread_id Nullable(string),
	wb_run_step Nullable(UInt64),
	
	exception Nullable(string),
	display_name Nullable(string),
	
	-- data-skipping indexes
    INDEX idx_trace_id  trace_id  TYPE bloom_filter(0.001) GRANULARITY 4,
    INDEX idx_op_name   op_name   TYPE bloom_filter(0.001) GRANULARITY 4,
    INDEX idx_parent_id parent_id TYPE bloom_filter(0.001) GRANULARITY 4
	
) ENGINE = MergeTree
ORDER BY (project_id, reverse_timestamp, id)
PARTITION BY toYYYYMM(started_at)
PRIMARY KEY (project_id, id)
SETTINGS min_bytes_for_wide_part=0