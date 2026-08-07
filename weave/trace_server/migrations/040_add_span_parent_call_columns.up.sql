-- Link a @weave.op call to the agent spans it produced. The SDK stamps
-- weave.parent_call.id / weave.parent_call.trace_id on spans that start while
-- a call is running, and these columns are the promoted form. Populated going
-- forward only, while `spans` remains the source of truth.
--
-- bloom_filter(0.001) rather than the 0.01 of idx_eval_run_id in 037: both
-- columns hold high-cardinality random ids, so a tighter filter pays for
-- itself the same way it does on calls_complete.trace_id in 036. On the
-- linkage benchmark 0.001 costs 22 granules against a 19-granule baseline,
-- where 0.01 costs ~41.
ALTER TABLE spans
    ADD COLUMN IF NOT EXISTS parent_call_id       String DEFAULT '',
    ADD COLUMN IF NOT EXISTS parent_call_trace_id String DEFAULT '';

ALTER TABLE spans
    ADD INDEX IF NOT EXISTS idx_parent_call_id
        parent_call_id TYPE bloom_filter(0.001) GRANULARITY 1,
    ADD INDEX IF NOT EXISTS idx_parent_call_trace_id
        parent_call_trace_id TYPE bloom_filter(0.001) GRANULARITY 1;
