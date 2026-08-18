-- Populated only under `scope: category`; global runs leave every row ''.
ALTER TABLE signature_clusters
    ADD COLUMN IF NOT EXISTS category LowCardinality(String) DEFAULT '' AFTER topic_id;
