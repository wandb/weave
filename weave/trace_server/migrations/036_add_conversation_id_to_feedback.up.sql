/*
Denormalize the conversation a feedback row belongs to, so we can filter agent
conversations by signal (tags/ratings) without joining the `spans` table.
Populated going forward only; `spans` remains the source of truth. Mirrors the
existing span_* denormalization (migration 033).
*/
ALTER TABLE feedback ADD COLUMN IF NOT EXISTS conversation_id String DEFAULT '';

/*
Data-skipping index so `has(scorer_tags, ...)` / `hasAny(scorer_tags, [...])`
in the signal subquery can skip granules with no matching tag.
*/
ALTER TABLE feedback
    ADD INDEX IF NOT EXISTS idx_scorer_tags scorer_tags TYPE bloom_filter(0.01) GRANULARITY 1;
