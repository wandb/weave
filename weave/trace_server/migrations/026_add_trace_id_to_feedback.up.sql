-- Add trace_id column to feedback table for efficient per-trace aggregation
-- in feedback-based alerts. Populated at write time from the call referenced
-- by weave_ref. Does not change ORDER BY (would require table rebuild).
ALTER TABLE feedback ADD COLUMN IF NOT EXISTS trace_id Nullable(String) DEFAULT NULL;
