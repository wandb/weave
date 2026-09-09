ALTER TABLE signature_cluster_runs
    DROP COLUMN IF EXISTS failure_code,
    DROP COLUMN IF EXISTS truncated,
    DROP COLUMN IF EXISTS skipped_generation_count,
    DROP COLUMN IF EXISTS noise_count,
    DROP COLUMN IF EXISTS cluster_count,
    DROP COLUMN IF EXISTS signature_count;
