ALTER TABLE spans
    DROP INDEX IF EXISTS idx_eval_run_id;

ALTER TABLE spans
    DROP COLUMN IF EXISTS eval_run_id,
    DROP COLUMN IF EXISTS eval_predict_and_score_call_id,
    DROP COLUMN IF EXISTS eval_kind,
    DROP COLUMN IF EXISTS eval_row_digest,
    DROP COLUMN IF EXISTS eval_example_id,
    DROP COLUMN IF EXISTS eval_trial_index,
    DROP COLUMN IF EXISTS eval_evaluation_name;
