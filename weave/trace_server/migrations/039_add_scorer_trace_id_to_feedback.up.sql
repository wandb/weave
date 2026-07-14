/*
Denormalize the trace the scorer (judge) itself ran under, so signals can price
each invocation by reading total_cost_usd off the judge's own agent span
(joined on spans.trace_id) instead of the `calls` model. Populated going
forward only, while `spans` remains the source of truth. Mirrors the existing
span_* / span_trace_id denormalization (migrations 033, 038).

Distinct from span_trace_id: span_trace_id is the trace being scored (the
agent turn), scorer_trace_id is the trace that did the scoring (the judge LLM
call). No index: it is projected out and resolved against spans.trace_id, which
already carries its own bloom-filter index (migration 030, inline on the spans
table).
*/
ALTER TABLE feedback ADD COLUMN IF NOT EXISTS scorer_trace_id String DEFAULT '';
