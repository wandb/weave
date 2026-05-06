-- Migration 031: Persist summary.weave.status for call filtering/sorting.
--
-- This moves the status derivation out of hot read queries. The legacy
-- call_parts/calls_merged path stores terminal status only. NULL means the call
-- has not ended yet and is read as "running".

ALTER TABLE call_parts
    ADD COLUMN IF NOT EXISTS status Nullable(String) DEFAULT multiIf(
        isNotNull(exception), 'error',
        ifNull(toInt64OrNull(coalesce(nullIf(JSON_VALUE(summary_dump, '$."status_counts"."error"'), 'null'), '')), 0) > 0, 'descendant_error',
        isNotNull(ended_at), 'success',
        CAST(NULL, 'Nullable(String)')
    );

ALTER TABLE call_parts MATERIALIZE COLUMN status SETTINGS mutations_sync = 1;

ALTER TABLE calls_merged
    ADD COLUMN IF NOT EXISTS status SimpleAggregateFunction(any, Nullable(String)) DEFAULT multiIf(
        isNotNull(exception), 'error',
        ifNull(toInt64OrNull(coalesce(nullIf(JSON_VALUE(summary_dump, '$."status_counts"."error"'), 'null'), '')), 0) > 0, 'descendant_error',
        isNotNull(ended_at), 'success',
        CAST(NULL, 'Nullable(String)')
    );

ALTER TABLE calls_merged_view MODIFY QUERY
    SELECT project_id,
        id,
        anySimpleState(wb_run_id) as wb_run_id,
        anySimpleState(wb_run_step) as wb_run_step,
        anySimpleState(wb_run_step_end) as wb_run_step_end,
        anySimpleStateIf(wb_user_id, isNotNull(call_parts.started_at)) as wb_user_id,
        anySimpleState(trace_id) as trace_id,
        anySimpleState(parent_id) as parent_id,
        anySimpleState(thread_id) as thread_id,
        anySimpleState(turn_id) as turn_id,
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
        argMaxState(display_name, call_parts.created_at) as display_name,
        anySimpleState(coalesce(call_parts.started_at, call_parts.ended_at, call_parts.created_at)) as sortable_datetime,
        anySimpleState(otel_dump) as otel_dump,
        minSimpleState(expire_at) as expire_at,
        anySimpleState(status) as status
    FROM call_parts
    GROUP BY project_id,
        id;

ALTER TABLE calls_merged MATERIALIZE COLUMN status SETTINGS mutations_sync = 1;

ALTER TABLE calls_complete
    ADD COLUMN IF NOT EXISTS status String DEFAULT multiIf(
        exception != '', 'error',
        ifNull(toInt64OrNull(coalesce(nullIf(JSON_VALUE(summary_dump, '$."status_counts"."error"'), 'null'), '')), 0) > 0, 'descendant_error',
        ended_at = toDateTime64(0, 6), 'running',
        'success'
    );

ALTER TABLE calls_complete MATERIALIZE COLUMN status SETTINGS mutations_sync = 1;
