CREATE TABLE calls_sorted
(
    project_id String,
    id String,
    trace_id Nullable(String),
    parent_id Nullable(String),
    op_name Nullable(String),
    started_at DateTime64(3),
    attributes_dump Nullable(String),
    inputs_dump Nullable(String),
    input_refs Array(String),
    ended_at DateTime64(3),
    output_dump Nullable(String),
    summary_dump Nullable(String),
    exception Nullable(String),
    output_refs Array(String),
    wb_user_id Nullable(String),
    wb_run_id Nullable(String),

    display_name Nullable(String),
    deleted_at Nullable(DateTime64(3))
)
ENGINE = MergeTree
-- You can also consider PARTITION BY something like toDate(started_at), etc.
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
    anyMerge(trace_id) AS trace_id,
    anyMerge(parent_id) AS parent_id,
    anyMerge(op_name) AS op_name,
    anyMerge(started_at) AS started_at,
    anyMerge(attributes_dump) AS attributes_dump,
    anyMerge(inputs_dump) AS inputs_dump,
    arrayConcatMerge(input_refs) AS input_refs,
    anyMerge(ended_at) AS ended_at,
    anyMerge(output_dump) AS output_dump,
    anyMerge(summary_dump) AS summary_dump,
    anyMerge(exception) AS exception,
    arrayConcatMerge(output_refs) AS output_refs,
    anyMerge(wb_user_id) AS wb_user_id,
    anyMerge(wb_run_id) AS wb_run_id,
    
    anyMerge(display_name) AS display_name,
    anyMerge(deleted_at) AS deleted_at
FROM calls_merged
GROUP BY
    project_id, 
    id;
    