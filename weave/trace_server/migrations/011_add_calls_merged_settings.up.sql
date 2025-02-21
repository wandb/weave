ALTER TABLE calls_merged
    MODIFY SETTING min_bytes_for_wide_part = 0, min_age_to_force_merge_seconds = 30;