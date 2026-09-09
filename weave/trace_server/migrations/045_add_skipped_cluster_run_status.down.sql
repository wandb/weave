-- Rows holding 'skipped' would fail this cast, so they are rewritten first.
ALTER TABLE signature_cluster_runs
    UPDATE status = 'canceled' WHERE status = 'skipped';
ALTER TABLE signature_cluster_runs
    MODIFY COLUMN status Enum8('pending' = 1, 'running' = 2, 'succeeded' = 3, 'failed' = 4, 'canceled' = 5)
        DEFAULT 'pending';
