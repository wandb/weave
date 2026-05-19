-- Migration 031: Add ngram bloom filter indexes on
-- ifNull(inputs_dump, ''), ifNull(output_dump, ''),
-- ifNull(summary_dump, ''), and ifNull(attributes_dump, '') to
-- accelerate substring filters over the pre-aggregation calls_merged rows.
--
-- The optimization_builder emits `ifNull(calls_merged.<dump>, '') LIKE ...`
-- for heavy-field eq/contains/in filters before GROUP BY. Matching the index
-- expression character-for-character lets ClickHouse prune granules instead
-- of scanning the full column for every query.
--
-- ngrambf_v1(5, 65536, 3, 0): 5-char n-grams, 65536-byte filter per index
-- entry, 3 hash functions, random seed 0.
--
-- n=5 is a deliberate compromise. n=4 generates ~100x more distinct tokens
-- per granule than n=5 over large JSON blobs and saturates 65536-byte
-- filters in practice (measured via data_skipping_indices compression
-- ratio). n=6 would make any LIKE fragment shorter than 6 chars
-- uncoverable by the index, including short quoted string values from
-- `_create_like_pattern_for_value` like `"hi"` (4 chars). n=5 keeps
-- ~4-char values covered once the surrounding `"` quotes are included
-- (`"hi"` is 4 chars, below, `"abcd"` is 6, above) while still roughly
-- halving the token space vs n=4.
--
-- GRANULARITY 8: each bloom filter covers 8 table granules (~64K rows).
-- A 64KB ngrambf_v1 filter saturates within 1-2 granules of large JSON
-- blobs, so finer granularity (GRANULARITY 1-2) buys little additional
-- pruning while inflating index size and lookup cost ~8x. Coarser keeps
-- the index small enough to stay hot in RAM and amortizes the filter probe
-- across more rows.
--
-- Lazy backfill: we deliberately skip MATERIALIZE INDEX. On a large
-- calls_merged that would block the migration on full-table reindexing
-- and compete with ingest. Instead the index is populated as parts are
-- naturally re-merged. New parts get the index from the moment this
-- migration applies, and existing parts gain it over time. Operators
-- who want immediate coverage can run MATERIALIZE INDEX on each index
-- name out-of-band.
ALTER TABLE calls_merged
    ADD INDEX IF NOT EXISTS idx_inputs_dump_ngram
        ifNull(inputs_dump, '') TYPE ngrambf_v1(5, 65536, 3, 0) GRANULARITY 8;

ALTER TABLE calls_merged
    ADD INDEX IF NOT EXISTS idx_output_dump_ngram
        ifNull(output_dump, '') TYPE ngrambf_v1(5, 65536, 3, 0) GRANULARITY 8;

ALTER TABLE calls_merged
    ADD INDEX IF NOT EXISTS idx_summary_dump_ngram
        ifNull(summary_dump, '') TYPE ngrambf_v1(5, 65536, 3, 0) GRANULARITY 8;

ALTER TABLE calls_merged
    ADD INDEX IF NOT EXISTS idx_attributes_dump_ngram
        ifNull(attributes_dump, '') TYPE ngrambf_v1(5, 65536, 3, 0) GRANULARITY 8;
