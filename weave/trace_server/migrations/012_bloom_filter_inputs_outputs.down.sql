ALTER TABLE calls_merged
    ADD INDEX bf_inputs_dump inputs_dump TYPE BLOOM_FILTER GRANULARITY 1;

ALTER TABLE calls_merged
    ADD INDEX bf_output_dump output_dump TYPE BLOOM_FILTER GRANULARITY 1;

ALTER TABLE calls_merged MATERLIAZE INDEX bf_inputs_dump;
ALTER TABLE calls_merged MATERLIAZE INDEX bf_output_dump;
