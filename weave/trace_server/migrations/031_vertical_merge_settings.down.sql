-- Rollback Migration 031: reset vertical-merge tuning to cluster defaults.

ALTER TABLE call_parts
    RESET SETTING
        vertical_merge_algorithm_min_columns_to_activate,
        vertical_merge_algorithm_min_rows_to_activate,
        vertical_merge_algorithm_min_bytes_to_activate,
        merge_max_block_size;

ALTER TABLE calls_merged
    RESET SETTING
        vertical_merge_algorithm_min_columns_to_activate,
        vertical_merge_algorithm_min_rows_to_activate,
        vertical_merge_algorithm_min_bytes_to_activate,
        merge_max_block_size;

ALTER TABLE calls_complete
    RESET SETTING
        vertical_merge_algorithm_min_columns_to_activate,
        vertical_merge_algorithm_min_rows_to_activate,
        vertical_merge_algorithm_min_bytes_to_activate,
        merge_max_block_size;
