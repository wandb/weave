ALTER TABLE feedback DROP INDEX IF EXISTS idx_scorer_tags;
ALTER TABLE feedback DROP COLUMN IF EXISTS conversation_id;
