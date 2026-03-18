ALTER TABLE genai_spans
    DROP COLUMN IF EXISTS reasoning_tokens,
    DROP COLUMN IF EXISTS reasoning_content,
    DROP COLUMN IF EXISTS tool_definitions,
    DROP COLUMN IF EXISTS compaction_summary,
    DROP COLUMN IF EXISTS compaction_items_before,
    DROP COLUMN IF EXISTS compaction_items_after;
