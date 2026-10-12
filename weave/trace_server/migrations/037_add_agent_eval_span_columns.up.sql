ALTER TABLE spans
    ADD COLUMN IF NOT EXISTS eval_run_id                    String DEFAULT '',
    ADD COLUMN IF NOT EXISTS eval_predict_and_score_call_id String DEFAULT '',
    ADD COLUMN IF NOT EXISTS eval_kind                      LowCardinality(String) DEFAULT '',
    ADD COLUMN IF NOT EXISTS eval_row_digest                String DEFAULT '',
    ADD COLUMN IF NOT EXISTS eval_example_id                String DEFAULT '',
    ADD COLUMN IF NOT EXISTS eval_trial_index               Int32 DEFAULT -1,
    ADD COLUMN IF NOT EXISTS eval_evaluation_name           String DEFAULT '';

-- Only eval_run_id gets a skip index: it's the column the Agents UI filters
-- eval runs on. The other eval columns are either looked up alongside
-- eval_run_id (already narrowed to a handful of granules) or too rare to earn
-- back the insert+read cost of a skip index -- in a project with evals, far
-- fewer than one row per granule belongs to an eval, so those indexes would
-- rarely skip anything.
ALTER TABLE spans
    ADD INDEX IF NOT EXISTS idx_eval_run_id eval_run_id TYPE bloom_filter(0.01) GRANULARITY 1;
