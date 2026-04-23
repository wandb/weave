-- Migration 031: Add ngram bloom filter index on ifNull(inputs_dump, '')
-- to accelerate substring filters over the pre-aggregation calls_merged rows.
--
-- The optimization_builder emits `ifNull(calls_merged.inputs_dump, '') LIKE ...`
-- for heavy-field eq/contains/in filters before GROUP BY. Matching the index
-- expression character-for-character lets ClickHouse prune granules instead
-- of scanning the full inputs_dump column for every query.
--
-- ngrambf_v1(4, 65536, 3, 0): 4-char n-grams, 65536-bit filter per granule,
-- 3 hash functions, random seed 0. 4-char n-grams match the smallest useful
-- LIKE fragment the builder emits.
ALTER TABLE calls_merged
    ADD INDEX IF NOT EXISTS idx_inputs_dump_ngram
        ifNull(inputs_dump, '') TYPE ngrambf_v1(4, 65536, 3, 0) GRANULARITY 1
    SETTINGS alter_sync = 1;
