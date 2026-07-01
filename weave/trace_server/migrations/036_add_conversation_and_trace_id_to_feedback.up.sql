/*
Denormalize the conversation and turn a feedback row belongs to, so we can
filter agent conversations (by conversation_id) and, later, agent spans (by
trace_id) on signals without joining the `spans` table. Populated going
forward only; `spans` remains the source of truth. Mirrors the existing
span_* denormalization (migration 033).

Conversation-targeted feedback has a conversation_id but no single trace_id;
turn/span-targeted feedback carries both.
*/
ALTER TABLE feedback ADD COLUMN IF NOT EXISTS conversation_id String DEFAULT '';
ALTER TABLE feedback ADD COLUMN IF NOT EXISTS trace_id String DEFAULT '';

/*
Data-skipping index so `has(scorer_tags, ...)` / `hasAny(scorer_tags, [...])`
in the signal subquery can skip granules with no matching tag. conversation_id
and trace_id are projected out of the subquery, not filtered on, so they need
no index here.
*/
ALTER TABLE feedback
    ADD INDEX IF NOT EXISTS idx_scorer_tags scorer_tags TYPE bloom_filter(0.01) GRANULARITY 1;
