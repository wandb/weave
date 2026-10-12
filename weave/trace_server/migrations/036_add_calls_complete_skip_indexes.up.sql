-- Migration 036: tune skip indexes on calls_complete for two hot filter shapes.
--
-- idx_trace_id_bloom: the existing idx_trace_id uses the default 0.025
-- false-positive rate, which leaves ~43% of granules for a multi-value
-- `trace_id IN (...)` fetch (survival is 1-(1-0.025)^N). A 0.001 filter drops
-- that to ~2%. Kept alongside idx_trace_id so existing (un-materialized) parts
-- still prune on the coarse index.
--
-- idx_attributes_dump: attributes_dump is the only *_dump column without a tokenbf,
-- so the `attributes_dump LIKE '%"value"%'` custom-attribute optimization (e.g. a
-- conversation_id lookup) has no index to prune on and scans the started_at window.
-- This mirrors idx_inputs_dump / idx_output_dump / idx_summary_dump.
--
-- Intentionally NOT materialized: applies to new and newly-merged parts going
-- forward, avoiding a full-column reindex mutation on large existing tables.
ALTER TABLE calls_complete
    ADD INDEX IF NOT EXISTS idx_trace_id_bloom
        trace_id TYPE bloom_filter(0.001) GRANULARITY 1
    SETTINGS alter_sync = 1;

ALTER TABLE calls_complete
    ADD INDEX IF NOT EXISTS idx_attributes_dump
        attributes_dump TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1
    SETTINGS alter_sync = 1;
