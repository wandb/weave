-- Add column and backfill call_id for all rows that have a call_ref, the id is everything after the last '/'
-- example: weave-trace-internal:///UHJvamVjdEludGVybmFsSWQ6MTA0MzQwOA==/call/0194f9bc-3347-7920-970e-580ac9ad21ed --> 0194f9bc-3347-7920-970e-580ac9ad21ed 
ALTER TABLE feedback ADD COLUMN call_id String MATERIALIZED reverse(substring(reverse(call_ref), 1, position(reverse(call_ref), '/') - 1));
