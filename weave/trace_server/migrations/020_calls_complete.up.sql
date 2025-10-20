CREATE TABLE calls_complete (
    id              String,
    project_id      String,
    created_at      DateTime64(3) DEFAULT now64(3),

    trace_id        String,
    op_name         String,
    started_at      DateTime64(6),
    ended_at        DateTime64(6),

    parent_id       Nullable(String),
    display_name    Nullable(String) DEFAULT NULL,
    
    attributes_dump Nullable(String),
    inputs_dump     Nullable(String),
    input_refs      Array(String),
    output_dump     Nullable(String),
    summary_dump    Nullable(String),
    exception       Nullable(String),
    output_refs     Array(String),

    wb_user_id      Nullable(String),
    wb_run_id       Nullable(String),
    wb_run_step     Nullable(UInt64) DEFAULT NULL,
    wb_run_step_end Nullable(UInt64) DEFAULT NULL,

    thread_id       Nullable(String) DEFAULT NULL,
    turn_id         Nullable(String) DEFAULT NULL,
    

    INDEX idx_wb_run_id wb_run_id TYPE set(100) GRANULARITY 1,
    INDEX idx_thread_id thread_id TYPE set(100) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE set(100) GRANULARITY 1,
    INDEX idx_op_name op_name TYPE set(100) GRANULARITY 1,
    INDEX idx_ended_at ended_at TYPE minmax GRANULARITY 1
) ENGINE = MergeTree
ORDER BY (project_id, started_at, id);

CREATE TABLE call_starts (
    id              String,
    project_id      String,
    created_at      DateTime64(3) DEFAULT now64(3),

    trace_id        String,
    op_name         String,
    started_at      DateTime64(6),

    parent_id       Nullable(String),
    display_name    Nullable(String) DEFAULT NULL,
    
    attributes_dump Nullable(String),
    inputs_dump     Nullable(String),
    input_refs      Array(String),

    wb_user_id      Nullable(String),
    wb_run_id       Nullable(String),
    wb_run_step     Nullable(UInt64) DEFAULT NULL,
    wb_run_step_end Nullable(UInt64) DEFAULT NULL,

    thread_id       Nullable(String) DEFAULT NULL,
    turn_id         Nullable(String) DEFAULT NULL,

    INDEX idx_wb_run_id wb_run_id TYPE set(100) GRANULARITY 1,
    INDEX idx_thread_id thread_id TYPE set(100) GRANULARITY 1,
    INDEX idx_trace_id trace_id TYPE set(100) GRANULARITY 1,
    INDEX idx_op_name op_name TYPE set(100) GRANULARITY 1
) ENGINE = MergeTree
ORDER BY (project_id, started_at, id);

-- Drop the existing materialized view if it exists
DROP VIEW IF EXISTS calls_merged_view;

-- Create new materialized view that unions both tables
CREATE MATERIALIZED VIEW calls_merged_view TO calls_merged AS
SELECT 
    project_id,
    id,
    anySimpleState(wb_run_id) as wb_run_id,
    anySimpleState(wb_user_id) as wb_user_id,
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
    argMaxState(display_name, created_at) as display_name,
    anySimpleState(coalesce(combined_calls.started_at, combined_calls.ended_at, combined_calls.created_at)) as sortable_datetime,
    anySimpleState(wb_run_step) as wb_run_step,
    anySimpleState(wb_run_step_end) as wb_run_step_end,
    anySimpleState(thread_id) as thread_id,
    anySimpleState(turn_id) as turn_id
FROM (
    SELECT 
        id, project_id, created_at, trace_id, op_name, started_at,
        ended_at, parent_id, display_name, attributes_dump, 
        inputs_dump, input_refs, output_dump, summary_dump, 
        exception, output_refs, wb_user_id, wb_run_id, wb_run_step, 
        wb_run_step_end, thread_id, turn_id
    FROM calls_complete
    UNION ALL
    SELECT 
        id, project_id, created_at, trace_id, op_name, started_at,
        NULL as ended_at, parent_id, display_name, attributes_dump, 
        inputs_dump, input_refs, NULL as output_dump, NULL as summary_dump, 
        NULL as exception, [] as output_refs, wb_user_id, wb_run_id, wb_run_step, 
        NULL as wb_run_step_end, thread_id, turn_id
    FROM call_starts
) AS combined_calls
GROUP BY project_id, id;

CREATE TABLE calls_complete_stats
(
    project_id String,
    id String,
    trace_id SimpleAggregateFunction(any, String),
    parent_id SimpleAggregateFunction(any, Nullable(String)),
    op_name SimpleAggregateFunction(any, String),
    started_at SimpleAggregateFunction(any, DateTime64(6)),
    ended_at SimpleAggregateFunction(any, DateTime64(6)),
    attributes_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    inputs_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    output_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    summary_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    exception_size_bytes SimpleAggregateFunction(any, Nullable(UInt64)),
    wb_user_id SimpleAggregateFunction(any, Nullable(String)),
    wb_run_id SimpleAggregateFunction(any, Nullable(String)),
    wb_run_step SimpleAggregateFunction(any, Nullable(UInt64)),
    wb_run_step_end SimpleAggregateFunction(any, Nullable(UInt64)),
    thread_id SimpleAggregateFunction(any, Nullable(String)),
    turn_id SimpleAggregateFunction(any, Nullable(String)),
    created_at SimpleAggregateFunction(min, DateTime64(3)),
    updated_at SimpleAggregateFunction(max, DateTime64(3)),
    display_name AggregateFunction(argMax, Nullable(String), DateTime64(3))
) ENGINE = AggregatingMergeTree()
ORDER BY (project_id, id);

CREATE MATERIALIZED VIEW calls_complete_stats_view
TO calls_complete_stats
AS
SELECT
    calls_complete.project_id,
    calls_complete.id,
    anySimpleState(calls_complete.trace_id) as trace_id,
    anySimpleState(calls_complete.parent_id) as parent_id,
    anySimpleState(calls_complete.op_name) as op_name,
    anySimpleState(calls_complete.started_at) as started_at,
    anySimpleState(calls_complete.ended_at) as ended_at,
    anySimpleState(length(calls_complete.attributes_dump)) as attributes_size_bytes,
    anySimpleState(length(calls_complete.inputs_dump)) as inputs_size_bytes,
    anySimpleState(length(calls_complete.output_dump)) as output_size_bytes,
    anySimpleState(length(calls_complete.summary_dump)) as summary_size_bytes,
    anySimpleState(length(calls_complete.exception)) as exception_size_bytes,
    anySimpleState(calls_complete.wb_user_id) as wb_user_id,
    anySimpleState(calls_complete.wb_run_id) as wb_run_id,
    anySimpleState(calls_complete.wb_run_step) as wb_run_step,
    anySimpleState(calls_complete.wb_run_step_end) as wb_run_step_end,
    anySimpleState(calls_complete.thread_id) as thread_id,
    anySimpleState(calls_complete.turn_id) as turn_id,
    minSimpleState(calls_complete.created_at) as created_at,
    maxSimpleState(calls_complete.created_at) as updated_at,
    argMaxState(calls_complete.display_name, calls_complete.created_at) as display_name
FROM calls_complete
GROUP BY
    calls_complete.project_id,
    calls_complete.id;