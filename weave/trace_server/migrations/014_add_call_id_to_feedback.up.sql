-- Add column and backfill weave_ref_id for all rows that have a weave_ref, the id is everything after the last '/'
-- example: weave-trace-internal:///UHJvamVjdEludGVybmFsSWQ6MTA0MzQwOA==/call/0194f9bc-3347-7920-970e-580ac9ad21ed --> 0194f9bc-3347-7920-970e-580ac9ad21ed 
ALTER TABLE feedback ADD COLUMN weave_ref_id String MATERIALIZED coalesce(regexpExtract(weave_ref, '/([^/]+)$'), '');
