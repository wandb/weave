-- Remove the rows inserted by the backfill (identifiable by the epoch
-- created_at). Real obj_create alias writes carry now64(3) timestamps.
ALTER TABLE aliases DELETE
WHERE alias = 'latest'
  AND created_at = toDateTime64('1970-01-01 00:00:00.001', 3);
