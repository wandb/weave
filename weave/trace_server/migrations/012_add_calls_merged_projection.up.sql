ALTER TABLE calls_merged
ADD PROJECTION reverse_timestamp
(
    SELECT
        project_id,
        id,
        wb_run_id,
        wb_user_id,
        trace_id,
        parent_id,
        op_name,
        started_at,
        attributes_dump,
        inputs_dump,
        output_dump,
        summary_dump,
        exception,
        output_refs,
        input_refs,
        ended_at,
        deleted_at,
        display_name
    ORDER BY (project_id, -toUnixTimestamp64Milli(started_at))
);
ALTER TABLE calls_merged MATERIALIZE PROJECTION reverse_timestamp;

