-- Remove the rows inserted by the backfill. Identified by the sentinel
-- wb_user_id; the epoch created_at is also matched as a belt-and-braces
-- guard. Real obj_create alias writes never set wb_user_id to this value.
ALTER TABLE aliases DELETE
WHERE alias = 'latest'
  AND wb_user_id = '__weave_backfill_031__'
  AND created_at = toDateTime64('1970-01-01 00:00:00.001', 3);
