/*
Add new microsecond-precision timestamp columns alongside existing columns
*/
ALTER TABLE call_parts
    ADD COLUMN started_at_micros Nullable(DateTime64(6)),
    ADD COLUMN ended_at_micros Nullable(DateTime64(6));

ALTER TABLE calls_merged
    ADD COLUMN started_at_micros SimpleAggregateFunction(any, Nullable(DateTime64(6))),
    ADD COLUMN ended_at_micros SimpleAggregateFunction(any, Nullable(DateTime64(6)));


ALTER TABLE calls_merged_view MODIFY QUERY
    SELECT project_id,
        -- **** Original query fields from migration 001 ****
        id,
        anySimpleState(wb_run_id) as wb_run_id,
        -- *** Ensure wb_user_id is grabbed from valid call rather than deleted row ***
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
        -- **** Add deleted_at to the view, added in migration 002 ****
        anySimpleState(deleted_at) as deleted_at,
        -- *** Add argMax to use most recent display_name from migration 004 ***
        argMaxState(display_name, call_parts.created_at) as display_name,
        -- **** Add microsecond-precision timestamp columns  ****
        anySimpleState(started_at_micros) as started_at_micros,
        anySimpleState(ended_at_micros) as ended_at_micros
    FROM call_parts
    GROUP BY project_id,
        id;