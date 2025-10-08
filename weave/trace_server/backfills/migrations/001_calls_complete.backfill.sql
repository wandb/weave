-- BACKFILL_VERSION: 1.0
-- CHECKPOINT_COLUMNS: sortable_datetime, project_id, id
-- DESCRIPTION: Backfill calls_complete from calls_merged using time-based batching

/*
TIME-BASED BATCHING APPROACH:

1. Use sortable_datetime index for efficient time-based filtering
2. Process data in time chunks to avoid loading entire table
3. Checkpoint tracks: last_processed_time, project_id, id
4. Each batch processes a specific time range

Framework provides: {db}, {batch_size}, {window_minutes}, {checkpoint_sortable_datetime}, {checkpoint_project_id}, {checkpoint_id}
*/

INSERT INTO {db}.calls_complete
SELECT 
    id,
    project_id,
    now64(3) as created_at,
    any(trace_id) as trace_id,
    any(op_name) as op_name,
    any(started_at) as started_at,
    any(ended_at) as ended_at,
    any(parent_id) as parent_id,
    argMaxMerge(display_name) as display_name,
    any(attributes_dump) as attributes_dump,
    any(inputs_dump) as inputs_dump,
    array_concat_agg(input_refs) as input_refs,
    any(output_dump) as output_dump,
    any(summary_dump) as summary_dump,
    any(exception) as exception,
    array_concat_agg(output_refs) as output_refs,
    any(wb_user_id) as wb_user_id,
    any(wb_run_id) as wb_run_id,
    any(wb_run_step) as wb_run_step,
    any(wb_run_step_end) as wb_run_step_end,
    any(thread_id) as thread_id,
    any(turn_id) as turn_id
FROM {db}.calls_merged
WHERE sortable_datetime > '{checkpoint_sortable_datetime}'
  AND sortable_datetime < dateAdd(MINUTE, {window_minutes}, toDateTime64('{checkpoint_sortable_datetime}', 6))
  AND (project_id > '{checkpoint_project_id}' 
       OR (project_id = '{checkpoint_project_id}' AND id > '{checkpoint_id}'))
GROUP BY project_id, id
HAVING ended_at IS NOT NULL
ORDER BY any(sortable_datetime), project_id, id
LIMIT {batch_size};