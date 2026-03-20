ALTER TABLE genai_spans ADD COLUMN IF NOT EXISTS conversation_name String DEFAULT '' AFTER conversation_id;
