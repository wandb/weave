-- What observable result would satisfy the intent, judged for `information_request`
-- and `action_request` only. Empty on every other category and on older rows.
ALTER TABLE intent_signatures
    ADD COLUMN IF NOT EXISTS completion_criterion String DEFAULT '' AFTER signature;

-- Who negative sentiment is pointed at (agent, product, own_work, unclear).
ALTER TABLE intent_signatures
    ADD COLUMN IF NOT EXISTS sentiment_target LowCardinality(String) DEFAULT 'unclear' AFTER sentiment_rationale;

-- A short display title beside the longer `label` and `description`. Empty on rows
-- written before the namer produced one.
ALTER TABLE signature_clusters
    ADD COLUMN IF NOT EXISTS title String DEFAULT '' AFTER centroid;

-- Cosine to `centroid` alone says which cluster is nearest, not whether a new
-- signature is close enough: a tight topic admits at 0.85 where a loose one admits
-- at 0.6, so no global threshold fits both. This is the low-percentile member cosine
-- the fit admitted its own remainder against, stored so a reader can assign between
-- fits from `centroid` and this floor without the members. NaN on older rows.
ALTER TABLE signature_clusters
    ADD COLUMN IF NOT EXISTS admission_floor Float32 DEFAULT nan AFTER title;

-- A run that admitted a project but read too few signatures to fit ends here.
ALTER TABLE signature_cluster_runs
    MODIFY COLUMN status Enum8('pending' = 1, 'running' = 2, 'succeeded' = 3, 'failed' = 4, 'canceled' = 5, 'skipped' = 6)
        DEFAULT 'pending';
