/*
    Add display_name column to call_parts
    Add display_name argMax aggregation to calls_merged
    Add display_name argMaxState aggregation to calls_merged_view

    NOTE:
    * `argMaxState` is NOT simple and must be queried with `argMaxMerge` *
*/

ALTER TABLE call_parts
    ADD COLUMN display_name Nullable(String) DEFAULT NULL;

ALTER TABLE calls_merged
    ADD COLUMN display_name AggregateFunction(argMax, Nullable(String), DateTime64(3));

ALTER TABLE calls_merged_view MODIFY QUERY
    SELECT project_id,
        id,
        anySimpleState(wb_run_id) as wb_run_id,
        anySimpleStateIf(wb_user_id, isNotNull(call_parts.started_at)) as wb_user_id,
        anySimpleState(trace_id) as trace_id,
        anySimpleState(parent_id) as parent_id,
        anySimpleState(op_name) as op_name,
        anySimpleState(started_at) as started_at,
        anySimpleState(attributes_dump) as attributes_dump,
        anySimpleState(inputs_dump) as inputs_dump,
        array_concat_aggSimpleState(input_refs) as input_refs,
        anySimpleState(ended_at) as ended_at,
        anySimpleState(output_dump) as output_dump,
        anySimpleState(summary_dump) as summary_dump,
        anySimpleState(exception) as exception,
        array_concat_aggSimpleState(output_refs) as output_refs,
        anySimpleState(deleted_at) as deleted_at,
        -- *** Add argMax to use most recent display_name ***
        argMaxState(display_name, call_parts.created_at) as display_name
    FROM call_parts
    GROUP BY project_id,
        id;

