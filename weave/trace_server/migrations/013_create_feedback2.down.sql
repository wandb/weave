-- 1. Recreate the original table schema as `feedback_old`
CREATE TABLE feedback_old (
    id String,
    project_id String,
    weave_ref String,
    wb_user_id String,
    creator String NULL,
    created_at DateTime64(3) DEFAULT now64(3),
    feedback_type String,
    payload_dump String,
    annotation_ref Nullable(String) DEFAULT NULL,
    runnable_ref Nullable(String) DEFAULT NULL,
    call_ref Nullable(String) DEFAULT NULL,
    trigger_ref Nullable(String) DEFAULT NULL
) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, weave_ref, wb_user_id, id);

-- 2. Backfill from current `feedback` into `feedback_old`
INSERT INTO feedback_old (
    id, project_id, weave_ref, wb_user_id, creator, created_at,
    feedback_type, payload_dump, annotation_ref, runnable_ref,
    call_ref, trigger_ref
)
SELECT
    id, project_id, weave_ref, wb_user_id, creator, created_at,
    feedback_type, payload_dump, annotation_ref, runnable_ref,
    call_ref, trigger_ref
FROM feedback;

-- 3. Create a materialized view to mirror new inserts from `feedback` to `feedback_old`
CREATE MATERIALIZED VIEW feedback_down_mv
TO feedback_old
AS
SELECT
    id, project_id, weave_ref, wb_user_id, creator, created_at,
    feedback_type, payload_dump, annotation_ref, runnable_ref,
    call_ref, trigger_ref
FROM feedback;

-- 4. Drop current `feedback` table
DROP TABLE feedback;

-- 5. Rename old table back to `feedback`
RENAME TABLE feedback_old TO feedback;

-- 6. Drop materialized view
DROP TABLE feedback_down_mv;
