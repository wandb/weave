/*
    Update calls_merged and calls_merged_stats to use argMax for inputs/attributes/input_refs
    This allows call_end to overwrite call_start inputs/attributes/input_refs

    Following the pattern established by display_name in migration 004:
    - Change from SimpleAggregateFunction(any) to AggregateFunction(argMax) for inputs/attributes
    - Change from array_concat_agg to argMax for input_refs
    - Use argMaxState with tuple ordering: prefer records with ended_at (call_end), 
      then fall back to created_at as tie-breaker
    - This handles the case where call_end can arrive before call_start
    
    NOTE: argMaxState is NOT simple and must be queried with argMaxMerge
*/

-- ============================================================================
-- Update calls_merged (main data aggregation table)
-- ============================================================================

DROP VIEW calls_merged_view;
DROP TABLE calls_merged;

CREATE TABLE calls_merged (
    project_id String,
    id String,
    trace_id SimpleAggregateFunction(any, Nullable(String)),
    parent_id SimpleAggregateFunction(any, Nullable(String)),
    op_name SimpleAggregateFunction(any, Nullable(String)),
    started_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    -- Use argMax to prefer call_end values over call_start
    attributes_dump AggregateFunction(argMax, Nullable(String), Tuple(UInt8, DateTime64(3))),
    inputs_dump AggregateFunction(argMax, Nullable(String), Tuple(UInt8, DateTime64(3))),
    input_refs AggregateFunction(argMax, Array(String), Tuple(UInt8, DateTime64(3))),
    ended_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    output_dump SimpleAggregateFunction(any, Nullable(String)),
    summary_dump SimpleAggregateFunction(any, Nullable(String)),
    exception SimpleAggregateFunction(any, Nullable(String)),
    output_refs SimpleAggregateFunction(array_concat_agg, Array(String)),
    wb_user_id SimpleAggregateFunction(any, Nullable(String)),
    wb_run_id SimpleAggregateFunction(any, Nullable(String)),
    deleted_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    display_name AggregateFunction(argMax, Nullable(String), DateTime64(3))
) ENGINE = AggregatingMergeTree
ORDER BY (project_id, id);

CREATE MATERIALIZED VIEW calls_merged_view TO calls_merged AS
SELECT 
    project_id,
    id,
    anySimpleState(wb_run_id) as wb_run_id,
    anySimpleStateIf(wb_user_id, isNotNull(call_parts.started_at)) as wb_user_id,
    anySimpleState(trace_id) as trace_id,
    anySimpleState(parent_id) as parent_id,
    anySimpleState(op_name) as op_name,
    anySimpleState(started_at) as started_at,
    -- Prefer values from call_end (where ended_at is not null) over call_start
    -- Tuple ordering: (has_ended_at, created_at) so call_end wins even if it arrives first
    argMaxState(
        attributes_dump, 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as attributes_dump,
    argMaxState(
        inputs_dump, 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as inputs_dump,
    argMaxState(
        input_refs, 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as input_refs,
    anySimpleState(ended_at) as ended_at,
    anySimpleState(output_dump) as output_dump,
    anySimpleState(summary_dump) as summary_dump,
    anySimpleState(exception) as exception,
    array_concat_aggSimpleState(output_refs) as output_refs,
    anySimpleState(deleted_at) as deleted_at,
    argMaxState(display_name, call_parts.created_at) as display_name
FROM call_parts
GROUP BY project_id, id;

-- ============================================================================
-- Update calls_merged_stats (stats aggregation table)
-- ============================================================================

DROP VIEW calls_merged_stats_view;
DROP TABLE calls_merged_stats;

CREATE TABLE calls_merged_stats
(
    project_id String,
    id String,
    trace_id SimpleAggregateFunction(any, Nullable(String)),
    parent_id SimpleAggregateFunction(any, Nullable(String)),
    op_name SimpleAggregateFunction(any, Nullable(String)),
    started_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    -- Use argMax with tuple ordering to prefer call_end values over call_start
    attributes_size_bytes AggregateFunction(argMax, Nullable(UInt64), Tuple(UInt8, DateTime64(3))),
    inputs_size_bytes AggregateFunction(argMax, Nullable(UInt64), Tuple(UInt8, DateTime64(3))),
    ended_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    output_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    summary_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    exception_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    wb_user_id SimpleAggregateFunction(any, Nullable(String)),
    wb_run_id SimpleAggregateFunction(any, Nullable(String)),
    updated_at SimpleAggregateFunction(max, DateTime64(3)),
    deleted_at SimpleAggregateFunction(any, Nullable(DateTime64(3))),
    display_name AggregateFunction(argMax, Nullable(String), DateTime64(3))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, id);

CREATE MATERIALIZED VIEW calls_merged_stats_view
TO calls_merged_stats
AS
SELECT
    call_parts.project_id,
    call_parts.id,
    anySimpleState(call_parts.trace_id) as trace_id,
    anySimpleState(call_parts.parent_id) as parent_id,
    anySimpleState(call_parts.op_name) as op_name,
    anySimpleState(call_parts.started_at) as started_at,
    -- Prefer sizes from call_end (where ended_at is not null) over call_start
    argMaxState(
        length(call_parts.attributes_dump), 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as attributes_size_bytes,
    argMaxState(
        length(call_parts.inputs_dump), 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as inputs_size_bytes,
    anySimpleState(call_parts.ended_at) as ended_at,
    anySimpleState(length(call_parts.output_dump)) as output_size_bytes,
    anySimpleState(length(call_parts.summary_dump)) as summary_size_bytes,
    anySimpleState(length(call_parts.exception)) as exception_size_bytes,
    anySimpleState(call_parts.wb_user_id) as wb_user_id,
    anySimpleState(call_parts.wb_run_id) as wb_run_id,
    anySimpleState(call_parts.deleted_at) as deleted_at,
    maxSimpleState(call_parts.created_at) as updated_at,
    argMaxState(call_parts.display_name, call_parts.created_at) as display_name
FROM call_parts
GROUP BY
    call_parts.project_id,
    call_parts.id;
