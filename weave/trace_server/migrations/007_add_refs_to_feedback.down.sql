ALTER TABLE feedback 
    DROP COLUMN IF EXISTS annotation_ref,
    DROP COLUMN IF EXISTS runnable_ref,
    DROP COLUMN IF EXISTS call_ref,
    DROP COLUMN IF EXISTS trigger_ref;
