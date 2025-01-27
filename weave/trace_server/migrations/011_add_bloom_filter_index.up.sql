ALTER TABLE calls_merged
    ADD INDEX bf_inputs_dump inputs_dump TYPE bloom_filter GRANULARITY 1;

ALTER TABLE calls_merged
    ADD INDEX bf_output_dump output_dump TYPE bloom_filter GRANULARITY 1;

ALTER TABLE calls_merged
    MATERIALIZE INDEX bf_inputs_dump;

ALTER TABLE calls_merged
    MATERIALIZE INDEX bf_output_dump;

ALTER TABLE calls_merged
    ADD INDEX min_max_id_idx (project_id, id) TYPE minmax;

