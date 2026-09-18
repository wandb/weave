-- A short display title beside the longer `label` and `description`. Empty on rows
-- written before the namer produced one.
ALTER TABLE signature_clusters
    ADD COLUMN IF NOT EXISTS title String DEFAULT '' AFTER centroid;
