-- Migration 033: ngram bloom filter index on ifNull(attributes_dump, '') so
-- attributes substring filters on calls_merged prune granules instead of
-- scanning the column. The query layer (gated by WF_CALLS_MERGED_HEAVY_INDEXES)
-- emits the matching ifNull(...) LIKE inside the candidate-id CTE.
--
-- ngrambf_v1(5, 65536, 3, 0): n=5 halves the token space vs n=4 over large
-- JSON blobs while staying usable for short quoted values, GRANULARITY 8 keeps
-- the index small enough to stay hot in RAM.
--
-- Lazy backfill: no MATERIALIZE INDEX, which would block the migration on a
-- full-table reindex. New parts get the index immediately and existing parts
-- gain it as they re-merge. Run MATERIALIZE INDEX idx_attributes_dump_ngram
-- out-of-band for immediate coverage.
ALTER TABLE calls_merged
    ADD INDEX IF NOT EXISTS idx_attributes_dump_ngram
        ifNull(attributes_dump, '') TYPE ngrambf_v1(5, 65536, 3, 0) GRANULARITY 8;
