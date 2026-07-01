-- Add first-class eval linkage columns to agent spans.
--
-- These mirror the weave.eval.* OTel attributes stamped by SDK/eval integrations
-- so agent span queries can filter/group/sort by eval run, row, and trial
-- without scanning custom attribute maps.
ALTER TABLE spans
    ADD COLUMN IF NOT EXISTS eval_run_id                    String DEFAULT '',
    ADD COLUMN IF NOT EXISTS eval_predict_and_score_call_id String DEFAULT '',
    ADD COLUMN IF NOT EXISTS eval_kind                      String DEFAULT '',
    ADD COLUMN IF NOT EXISTS eval_row_digest                String DEFAULT '',
    ADD COLUMN IF NOT EXISTS eval_example_id                String DEFAULT '',
    ADD COLUMN IF NOT EXISTS eval_trial_index               Int64 DEFAULT -1,
    ADD COLUMN IF NOT EXISTS eval_evaluation_name           String DEFAULT '';

-- Exact ID-like fields use bloom filters; low-cardinality fields use set
-- indexes; the display name gets the same ngram index shape as agent_name.
ALTER TABLE spans
    ADD INDEX IF NOT EXISTS idx_eval_run_id eval_run_id TYPE bloom_filter(0.01) GRANULARITY 1,
    ADD INDEX IF NOT EXISTS idx_eval_predict_and_score_call_id eval_predict_and_score_call_id TYPE bloom_filter(0.01) GRANULARITY 1,
    ADD INDEX IF NOT EXISTS idx_eval_row_digest eval_row_digest TYPE bloom_filter(0.01) GRANULARITY 1,
    ADD INDEX IF NOT EXISTS idx_eval_example_id eval_example_id TYPE bloom_filter(0.01) GRANULARITY 1,
    ADD INDEX IF NOT EXISTS idx_eval_trial_index eval_trial_index TYPE set(128) GRANULARITY 1,
    ADD INDEX IF NOT EXISTS idx_eval_kind eval_kind TYPE set(16) GRANULARITY 1,
    ADD INDEX IF NOT EXISTS idx_eval_evaluation_name eval_evaluation_name TYPE ngrambf_v1(8, 10000, 3, 0) GRANULARITY 1;
