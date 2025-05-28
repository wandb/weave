CREATE TABLE feedback_temp (
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
    trigger_ref Nullable(String) DEFAULT NULL,

    -- Add column and backfill weave_ref_id for all rows that have a weave_ref, the id is everything after the last '/'
    -- example: weave-trace-internal:///UHJvamVjdEludGVybmFsSWQ6MTA0MzQwOA==/call/0194f9bc-3347-7920-970e-580ac9ad21ed --> 0194f9bc-3347-7920-970e-580ac9ad21ed 
    weave_ref_id String MATERIALIZED coalesce(reverse(substring(reverse(weave_ref), 1, position(reverse(weave_ref), '/') - 1)), '')
) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, weave_ref, weave_ref_id, wb_user_id, id);

-- Backfill into feedback_temp
INSERT INTO feedback_temp (
    id, project_id, weave_ref, wb_user_id, creator, created_at,
    feedback_type, payload_dump, annotation_ref, runnable_ref,
    call_ref, trigger_ref
)
SELECT
    id, project_id, weave_ref, wb_user_id, creator, created_at,
    feedback_type, payload_dump, annotation_ref, runnable_ref,
    call_ref, trigger_ref
FROM feedback;

-- Create a materialized view to sync new writes to new table
CREATE MATERIALIZED VIEW feedback_temp_mv
TO feedback_temp
AS
SELECT
    id, project_id, weave_ref, wb_user_id, creator, created_at,
    feedback_type, payload_dump, annotation_ref, runnable_ref,
    call_ref, trigger_ref
FROM feedback;

-- Drop the old table
DROP TABLE feedback;

-- Rename the new table to the old table name
RENAME TABLE feedback_temp TO feedback;

-- Drop the materialized view
DROP VIEW feedback_temp_mv;