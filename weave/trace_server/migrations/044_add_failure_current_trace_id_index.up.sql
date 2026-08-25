ALTER TABLE failure_signatures
    ADD INDEX IF NOT EXISTS idx_current_trace_id
        current_trace_id TYPE bloom_filter(0.01) GRANULARITY 1;
