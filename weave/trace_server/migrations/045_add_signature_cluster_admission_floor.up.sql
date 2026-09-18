-- The fitted-member cosine floor a wording had to reach to join the cluster by
-- centroid, so a reader can apply that admission rule against `centroid` without
-- the fitted members. NaN on rows written before the column existed.
ALTER TABLE signature_clusters
    ADD COLUMN IF NOT EXISTS admission_floor Float32 DEFAULT nan AFTER centroid;
