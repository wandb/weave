-- User Info
ALTER TABLE calls_raw
ADD COLUMN wb_user_id Nullable(String);
ALTER TABLE calls_merged
ADD COLUMN wb_user_id SimpleAggregateFunction(any, Nullable(String));
-- Run Info
ALTER TABLE calls_raw
ADD COLUMN wb_run_id Nullable(String);
ALTER TABLE calls_merged
ADD COLUMN wb_run_id SimpleAggregateFunction(any, Nullable(String));
-- Modify the view
ALTER TABLE calls_merged_view
MODIFY QUERY
SELECT project_id,
    id,
    anySimpleState(wb_run_id) as wb_run_id,
    anySimpleState(wb_user_id) as wb_user_id,
    anySimpleState(trace_id) as trace_id,
    anySimpleState(parent_id) as parent_id,
    anySimpleState(name) as name,
    anySimpleState(start_datetime) as start_datetime,
    anySimpleState(attributes_dump) as attributes_dump,
    anySimpleState(inputs_dump) as inputs_dump,
    array_concat_aggSimpleState(input_refs) as input_refs,
    anySimpleState(end_datetime) as end_datetime,
    anySimpleState(outputs_dump) as outputs_dump,
    anySimpleState(summary_dump) as summary_dump,
    anySimpleState(exception) as exception,
    array_concat_aggSimpleState(output_refs) as output_refs
FROM calls_raw
GROUP BY project_id,
    id;
