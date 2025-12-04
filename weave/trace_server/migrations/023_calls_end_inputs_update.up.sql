/*
    Update calls_merged and calls_merged_stats to use argMax for inputs/attributes
    This allows call_end to overwrite call_start inputs/attributes
    
    Strategy: Add new internal columns with _impl suffix that use argMax aggregation.
    The query layer will transparently use these new columns while maintaining the same interface.
    Old columns remain for backwards compatibility during migration.
    
    Following the pattern established by display_name in migration 004:
    - Add new columns with AggregateFunction(argMax) for inputs/attributes  
    - Use argMaxState with tuple ordering: prefer records with ended_at (call_end), 
      then fall back to created_at as tie-breaker
    - This handles the case where call_end can arrive before call_start
    
    NOTE: argMaxState is NOT simple and must be queried with argMaxMerge
*/

-- ============================================================================
-- Update calls_merged (main data aggregation table)
-- ============================================================================

-- Add new internal implementation columns with argMax aggregation
ALTER TABLE calls_merged 
    ADD COLUMN IF NOT EXISTS attributes_dump_impl AggregateFunction(argMax, Nullable(String), Tuple(UInt8, DateTime64(3))),
    ADD COLUMN IF NOT EXISTS inputs_dump_impl AggregateFunction(argMax, Nullable(String), Tuple(UInt8, DateTime64(3))),
    ADD COLUMN IF NOT EXISTS input_refs_impl AggregateFunction(argMax, String, Tuple(UInt8, DateTime64(3)));

-- Drop and recreate the materialized view to populate both old and new columns
DROP VIEW IF EXISTS calls_merged_view;

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
    -- Keep old columns populated for backwards compatibility
    anySimpleState(attributes_dump) as attributes_dump,
    anySimpleState(inputs_dump) as inputs_dump,
    array_concat_aggSimpleState(input_refs) as input_refs,
    -- New _impl columns with argMax: prefer call_end over call_start
    -- Tuple ordering: (has_ended_at, created_at) so call_end wins even if it arrives first
    argMaxState(
        attributes_dump, 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as attributes_dump_impl,
    argMaxState(
        inputs_dump, 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as inputs_dump_impl,
    -- For input_refs: serialize array to JSON string for argMax compatibility
    argMaxState(
        toJSONString(input_refs), 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as input_refs_impl,
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

-- Add new internal implementation columns with argMax aggregation
ALTER TABLE calls_merged_stats 
    ADD COLUMN IF NOT EXISTS attributes_size_bytes_impl AggregateFunction(argMax, Nullable(UInt64), Tuple(UInt8, DateTime64(3))),
    ADD COLUMN IF NOT EXISTS inputs_size_bytes_impl AggregateFunction(argMax, Nullable(UInt64), Tuple(UInt8, DateTime64(3)));

-- Drop and recreate the materialized view
DROP VIEW IF EXISTS calls_merged_stats_view;

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
    -- Keep old columns populated for backwards compatibility
    anySimpleState(length(call_parts.attributes_dump)) as attributes_size_bytes,
    anySimpleState(length(call_parts.inputs_dump)) as inputs_size_bytes,
    -- New _impl columns: prefer sizes from call_end over call_start
    argMaxState(
        length(call_parts.attributes_dump), 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as attributes_size_bytes_impl,
    argMaxState(
        length(call_parts.inputs_dump), 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as inputs_size_bytes_impl,
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

-- ============================================================================
-- Backfill existing data
-- ============================================================================

-- Backfill calls_merged _impl columns from call_parts
-- This ensures existing data gets the new argMax behavior
INSERT INTO calls_merged
SELECT 
    project_id,
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
    argMaxState(
        attributes_dump, 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as attributes_dump_impl,
    argMaxState(
        inputs_dump, 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as inputs_dump_impl,
    argMaxState(
        toJSONString(input_refs), 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as input_refs_impl,
    anySimpleState(ended_at) as ended_at,
    anySimpleState(output_dump) as output_dump,
    anySimpleState(summary_dump) as summary_dump,
    anySimpleState(exception) as exception,
    array_concat_aggSimpleState(output_refs) as output_refs,
    anySimpleState(deleted_at) as deleted_at,
    argMaxState(display_name, call_parts.created_at) as display_name
FROM call_parts
GROUP BY project_id, id;

-- Backfill calls_merged_stats _impl columns from call_parts
-- This ensures existing stats get the new argMax behavior
INSERT INTO calls_merged_stats
SELECT
    call_parts.project_id,
    call_parts.id,
    anySimpleState(call_parts.trace_id) as trace_id,
    anySimpleState(call_parts.parent_id) as parent_id,
    anySimpleState(call_parts.op_name) as op_name,
    anySimpleState(call_parts.started_at) as started_at,
    anySimpleState(length(call_parts.attributes_dump)) as attributes_size_bytes,
    anySimpleState(length(call_parts.inputs_dump)) as inputs_size_bytes,
    argMaxState(
        length(call_parts.attributes_dump), 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as attributes_size_bytes_impl,
    argMaxState(
        length(call_parts.inputs_dump), 
        tuple(if(isNotNull(call_parts.ended_at), 1, 0), call_parts.created_at)
    ) as inputs_size_bytes_impl,
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
