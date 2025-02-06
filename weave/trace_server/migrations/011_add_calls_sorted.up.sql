DROP TABLE IF EXISTS calls_sorted;
CREATE TABLE calls_sorted
(
    project_id String,
    id String,

    wb_run_id Nullable(String),
    wb_user_id Nullable(String),
    trace_id Nullable(String),  
    parent_id Nullable(String),
    op_name Nullable(String),
    started_at DateTime64(3),
    attributes_dump Nullable(String),
    inputs_dump Nullable(String),
    input_refs Array(String),
    ended_at Nullable(DateTime64(3)),
    output_dump Nullable(String),
    summary_dump Nullable(String),
    exception Nullable(String),
    output_refs Array(String),

    display_name Nullable(String),
    deleted_at Nullable(DateTime64(3))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, started_at);

--------------------------------------------------------------------------------
-- 2) Create a materialized view that merges the Aggregating states
--    in calls_merged into final (non-aggregate) values, inserting them
--    into the newly created calls_sorted table.
--------------------------------------------------------------------------------
CREATE MATERIALIZED VIEW calls_sorted_mv
TO calls_sorted
AS
SELECT
    project_id,
    id,
    -- Merge the aggregate states into final values:
    anySimpleState(trace_id) AS trace_id,
    anySimpleState(parent_id) AS parent_id,
    anySimpleState(op_name) AS op_name,
    coalesce(anySimpleState(calls_merged.started_at), coalesce(anySimpleState(calls_merged.ended_at), now64(3))) AS started_at,
    anySimpleState(attributes_dump) AS attributes_dump,
    anySimpleState(inputs_dump) AS inputs_dump,
    array_concat_aggSimpleState(input_refs) AS input_refs,
    anySimpleState(calls_merged.ended_at) AS ended_at,
    anySimpleState(output_dump) AS output_dump,
    anySimpleState(summary_dump) AS summary_dump,
    anySimpleState(exception) AS exception,
    array_concat_aggSimpleState(output_refs) AS output_refs,
    anySimpleState(wb_user_id) AS wb_user_id,
    anySimpleState(wb_run_id) AS wb_run_id,
    
    anySimpleState(display_name) AS display_name,
    anySimpleState(deleted_at) AS deleted_at
FROM calls_merged
GROUP BY
    project_id, 
    id;