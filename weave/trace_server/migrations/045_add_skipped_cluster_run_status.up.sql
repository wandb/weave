-- A run that admitted a project but read too few signatures to fit ends here.
ALTER TABLE signature_cluster_runs
    MODIFY COLUMN status Enum8('pending' = 1, 'running' = 2, 'succeeded' = 3, 'failed' = 4, 'canceled' = 5, 'skipped' = 6)
        DEFAULT 'pending';
