ALTER TABLE signature_cluster_runs
    ADD COLUMN IF NOT EXISTS signature_count UInt64 DEFAULT 0 AFTER status,
    ADD COLUMN IF NOT EXISTS cluster_count UInt32 DEFAULT 0 AFTER signature_count,
    ADD COLUMN IF NOT EXISTS noise_count UInt64 DEFAULT 0 AFTER cluster_count,
    ADD COLUMN IF NOT EXISTS skipped_generation_count UInt64 DEFAULT 0 AFTER noise_count,
    ADD COLUMN IF NOT EXISTS truncated Bool DEFAULT false AFTER skipped_generation_count,
    ADD COLUMN IF NOT EXISTS failure_code Nullable(Enum8(
        'no_signatures' = 1,
        'insufficient_signatures' = 2,
        'inference_unavailable' = 3,
        'storage_unavailable' = 4,
        'internal' = 5
    )) DEFAULT NULL AFTER truncated;
