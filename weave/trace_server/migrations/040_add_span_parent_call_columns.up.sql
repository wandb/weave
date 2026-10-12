ALTER TABLE spans
    ADD COLUMN IF NOT EXISTS parent_call_id       String DEFAULT '',
    ADD COLUMN IF NOT EXISTS parent_call_trace_id String DEFAULT '';

ALTER TABLE spans
    ADD INDEX IF NOT EXISTS idx_parent_call_id
        parent_call_id TYPE bloom_filter(0.001) GRANULARITY 1,
    ADD INDEX IF NOT EXISTS idx_parent_call_trace_id
        parent_call_trace_id TYPE bloom_filter(0.001) GRANULARITY 1;
