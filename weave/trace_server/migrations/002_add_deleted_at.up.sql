/*
This migration adds:
    * `deleted_at` to
        - the object_versions, call_parts, and calls_merged tables
        - the object_versions_deduped and calls_merged_view views
*/

ALTER TABLE object_versions
    ADD COLUMN deleted_at Nullable(DateTime64(3)) DEFAULT NULL;

ALTER TABLE call_parts
    ADD COLUMN deleted_at Nullable(DateTime64(3)) DEFAULT NULL;

ALTER TABLE calls_merged
    ADD COLUMN deleted_at SimpleAggregateFunction(any, Nullable(DateTime64(3)));

ALTER TABLE calls_merged_view MODIFY QUERY
    SELECT project_id,
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
        -- **** Add deleted_at to the view ****
        anySimpleState(deleted_at) as deleted_at
    FROM call_parts
    GROUP BY project_id,
        id;
