-- Add reasoning tokens, tool definitions, and compaction tracking columns
ALTER TABLE genai_spans
    ADD COLUMN IF NOT EXISTS reasoning_tokens      UInt64 DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reasoning_content     String DEFAULT '',
    ADD COLUMN IF NOT EXISTS tool_definitions      String DEFAULT '',
    ADD COLUMN IF NOT EXISTS compaction_summary    String DEFAULT '',
    ADD COLUMN IF NOT EXISTS compaction_items_before UInt32 DEFAULT 0,
    ADD COLUMN IF NOT EXISTS compaction_items_after  UInt32 DEFAULT 0;
