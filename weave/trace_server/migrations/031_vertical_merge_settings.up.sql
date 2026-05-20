-- Migration 031: Force vertical-merge algorithm on wide-row tables.
--
-- Only affects future merges. No data rewrite. Reversible via the .down.sql.
--
-- Background: on at least one production cluster a single Horizontal merge of
-- ~27 GB / 1.57M rows on `calls_merged` was observed running ~32 minutes at 28%
-- progress, with bytes_read_uncompressed / rows_read = ~17 KB/row. That is
-- exactly the wide-row case where the Vertical algorithm is dramatically
-- faster, but the cluster default `vertical_merge_algorithm_min_columns_to_activate=11`
-- was preventing it from being chosen.
--
-- Settings applied here:
--   vertical_merge_algorithm_min_columns_to_activate=1
--   vertical_merge_algorithm_min_rows_to_activate=1
--   vertical_merge_algorithm_min_bytes_to_activate=0
--   merge_max_block_size=65536           (default 8192; bigger blocks = better throughput per thread)
--
-- Worst-case if vertical is not actually faster on a given cluster: the next
-- merge picks vertical anyway and runs at roughly the same speed it would have
-- under horizontal. RESET SETTING on each column reverts.

ALTER TABLE call_parts
    MODIFY SETTING
        vertical_merge_algorithm_min_columns_to_activate = 1,
        vertical_merge_algorithm_min_rows_to_activate = 1,
        vertical_merge_algorithm_min_bytes_to_activate = 0,
        merge_max_block_size = 65536;

ALTER TABLE calls_merged
    MODIFY SETTING
        vertical_merge_algorithm_min_columns_to_activate = 1,
        vertical_merge_algorithm_min_rows_to_activate = 1,
        vertical_merge_algorithm_min_bytes_to_activate = 0,
        merge_max_block_size = 65536;

ALTER TABLE calls_complete
    MODIFY SETTING
        vertical_merge_algorithm_min_columns_to_activate = 1,
        vertical_merge_algorithm_min_rows_to_activate = 1,
        vertical_merge_algorithm_min_bytes_to_activate = 0,
        merge_max_block_size = 65536;
