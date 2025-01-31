ALTER TABLE calls_merged DROP PROJECTION IF EXISTS reverse_timestamp;
ALTER TABLE calls_merged DROP COLUMN IF EXISTS started_at_neg;

