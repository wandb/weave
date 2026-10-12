ALTER TABLE feedback DROP INDEX IF EXISTS idx_scorer_tags;
ALTER TABLE feedback DROP COLUMN IF EXISTS span_trace_id;
ALTER TABLE feedback DROP COLUMN IF EXISTS span_conversation_id;
