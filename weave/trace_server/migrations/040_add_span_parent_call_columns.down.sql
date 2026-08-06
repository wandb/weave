ALTER TABLE spans
    DROP INDEX IF EXISTS idx_parent_call_id,
    DROP INDEX IF EXISTS idx_parent_call_trace_id;

ALTER TABLE spans
    DROP COLUMN IF EXISTS parent_call_id,
    DROP COLUMN IF EXISTS parent_call_trace_id;
