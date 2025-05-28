-- Add column and backfill call_id for all rows that have a call_ref, the id is everything after the last '/'
-- example: weave-trace-internal:///UHJvamVjdEludGVybmFsSWQ6MTA0MzQwOA==/call/0194f9bc-3347-7920-970e-580ac9ad21ed --> 0194f9bc-3347-7920-970e-580ac9ad21ed 
ALTER TABLE feedback ADD COLUMN weave_ref_id String MATERIALIZED coalesce(reverse(substring(reverse(weave_ref), 1, position(reverse(weave_ref), '/') - 1)), '');
