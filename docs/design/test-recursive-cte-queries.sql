-- =============================================================================
-- Test Queries for Recursive CTE Aggregation in ClickHouse
-- =============================================================================
--
-- Run these in order to test recursive CTE functionality.
-- Replace {YOUR_PROJECT_ID} with an actual project_id from your data.
--
-- To find a project_id and trace with children:
-- SELECT project_id, trace_id, count() as call_count
-- FROM calls_complete
-- GROUP BY project_id, trace_id
-- HAVING call_count > 3
-- ORDER BY call_count DESC
-- LIMIT 10;

-- =============================================================================
-- STEP 0: Enable the analyzer (REQUIRED for recursive CTEs)
-- =============================================================================
SET enable_analyzer = 1;

-- =============================================================================
-- STEP 1: Find a good test trace (one with multiple levels)
-- =============================================================================
-- This finds traces with parent-child relationships
SELECT
    project_id,
    trace_id,
    count() as total_calls,
    countIf(parent_id IS NULL) as root_calls,
    countIf(parent_id IS NOT NULL) as child_calls,
    max(length(summary_dump)) as max_summary_size
FROM calls_complete
WHERE started_at > now() - INTERVAL 7 DAY  -- Recent data
GROUP BY project_id, trace_id
HAVING child_calls > 2  -- Has nested structure
ORDER BY total_calls DESC
LIMIT 10;

-- =============================================================================
-- STEP 2: Examine a specific trace's structure
-- =============================================================================
-- Replace these values with results from Step 1
-- SET param_project_id = 'your-entity/your-project';
-- SET param_trace_id = 'your-trace-id';

-- View the tree structure of a trace
SELECT
    id,
    parent_id,
    op_name,
    substring(summary_dump, 1, 100) as summary_preview,
    started_at,
    ended_at
FROM calls_complete
WHERE project_id = 'your-entity/your-project'  -- REPLACE THIS
  AND trace_id = 'your-trace-id'               -- REPLACE THIS
ORDER BY started_at;

-- =============================================================================
-- STEP 3: Simple recursive CTE - Find all descendants of a call
-- =============================================================================
-- This is the most basic recursive CTE test
-- Replace the project_id and root call id

WITH RECURSIVE
descendants AS (
    -- Base case: start with the root call
    SELECT
        id,
        parent_id,
        op_name,
        0 AS depth
    FROM calls_complete
    WHERE project_id = 'your-entity/your-project'  -- REPLACE
      AND parent_id IS NULL                         -- Start from root
      AND trace_id = 'your-trace-id'               -- REPLACE
    LIMIT 1  -- Just one root for testing

    UNION ALL

    -- Recursive case: find children
    SELECT
        c.id,
        c.parent_id,
        c.op_name,
        d.depth + 1
    FROM calls_complete c
    INNER JOIN descendants d ON c.parent_id = d.id
    WHERE c.project_id = 'your-entity/your-project'  -- REPLACE
      AND d.depth < 10  -- Safety limit
)
SELECT
    depth,
    id,
    parent_id,
    op_name
FROM descendants
ORDER BY depth, id;

-- =============================================================================
-- STEP 4: Recursive CTE with summary_dump extraction
-- =============================================================================
-- This tests JSON extraction combined with recursion

WITH RECURSIVE
descendants AS (
    SELECT
        id,
        parent_id,
        op_name,
        summary_dump,
        0 AS depth
    FROM calls_complete
    WHERE project_id = 'your-entity/your-project'  -- REPLACE
      AND parent_id IS NULL
      AND trace_id = 'your-trace-id'               -- REPLACE
    LIMIT 1

    UNION ALL

    SELECT
        c.id,
        c.parent_id,
        c.op_name,
        c.summary_dump,
        d.depth + 1
    FROM calls_complete c
    INNER JOIN descendants d ON c.parent_id = d.id
    WHERE c.project_id = 'your-entity/your-project'  -- REPLACE
      AND d.depth < 10
)
SELECT
    depth,
    op_name,
    -- Check if usage data exists
    JSONExtractRaw(summary_dump, 'usage') as usage_raw,
    -- Check what keys are in summary
    JSONExtractKeys(summary_dump) as summary_keys
FROM descendants
ORDER BY depth;

-- =============================================================================
-- STEP 5: Aggregate LLM usage across a trace
-- =============================================================================
-- This aggregates token counts from all calls in a trace

WITH RECURSIVE
descendants AS (
    SELECT
        id,
        parent_id,
        summary_dump,
        0 AS depth
    FROM calls_complete
    WHERE project_id = 'your-entity/your-project'  -- REPLACE
      AND parent_id IS NULL
      AND trace_id = 'your-trace-id'               -- REPLACE
    LIMIT 1

    UNION ALL

    SELECT
        c.id,
        c.parent_id,
        c.summary_dump,
        d.depth + 1
    FROM calls_complete c
    INNER JOIN descendants d ON c.parent_id = d.id
    WHERE c.project_id = 'your-entity/your-project'  -- REPLACE
      AND d.depth < 20
),
-- Extract usage JSON from each call
usage_data AS (
    SELECT
        id,
        depth,
        ifNull(JSONExtractRaw(summary_dump, 'usage'), '{}') as usage_raw
    FROM descendants
),
-- Explode to one row per model
usage_by_model AS (
    SELECT
        id,
        depth,
        kv.1 as model_id,
        JSONExtractInt(kv.2, 'requests') as requests,
        JSONExtractInt(kv.2, 'prompt_tokens') as prompt_tokens,
        JSONExtractInt(kv.2, 'completion_tokens') as completion_tokens,
        JSONExtractInt(kv.2, 'total_tokens') as total_tokens
    FROM usage_data
    ARRAY JOIN JSONExtractKeysAndValuesRaw(usage_raw) as kv
    WHERE usage_raw != '{}' AND usage_raw != ''
)
-- Aggregate by model
SELECT
    model_id,
    count() as call_count,
    sum(requests) as total_requests,
    sum(prompt_tokens) as total_prompt_tokens,
    sum(completion_tokens) as total_completion_tokens,
    sum(total_tokens) as total_total_tokens
FROM usage_by_model
WHERE model_id != ''
GROUP BY model_id
ORDER BY total_requests DESC;

-- =============================================================================
-- STEP 6: Aggregate latency statistics by op_name
-- =============================================================================

WITH RECURSIVE
descendants AS (
    SELECT
        id,
        parent_id,
        op_name,
        started_at,
        ended_at,
        0 AS depth
    FROM calls_complete
    WHERE project_id = 'your-entity/your-project'  -- REPLACE
      AND parent_id IS NULL
      AND trace_id = 'your-trace-id'               -- REPLACE
    LIMIT 1

    UNION ALL

    SELECT
        c.id,
        c.parent_id,
        c.op_name,
        c.started_at,
        c.ended_at,
        d.depth + 1
    FROM calls_complete c
    INNER JOIN descendants d ON c.parent_id = d.id
    WHERE c.project_id = 'your-entity/your-project'  -- REPLACE
      AND d.depth < 20
)
SELECT
    op_name,
    count() as call_count,
    round(avg(dateDiff('millisecond', started_at, ended_at)), 2) as avg_latency_ms,
    min(dateDiff('millisecond', started_at, ended_at)) as min_latency_ms,
    max(dateDiff('millisecond', started_at, ended_at)) as max_latency_ms
FROM descendants
WHERE ended_at IS NOT NULL
GROUP BY op_name
ORDER BY call_count DESC;

-- =============================================================================
-- STEP 7: Join with feedback table to aggregate scores
-- =============================================================================

WITH RECURSIVE
descendants AS (
    SELECT
        id,
        parent_id,
        op_name,
        0 AS depth
    FROM calls_complete
    WHERE project_id = 'your-entity/your-project'  -- REPLACE
      AND parent_id IS NULL
      AND trace_id = 'your-trace-id'               -- REPLACE
    LIMIT 1

    UNION ALL

    SELECT
        c.id,
        c.parent_id,
        c.op_name,
        d.depth + 1
    FROM calls_complete c
    INNER JOIN descendants d ON c.parent_id = d.id
    WHERE c.project_id = 'your-entity/your-project'  -- REPLACE
      AND d.depth < 20
),
-- Join with feedback
feedback_data AS (
    SELECT
        d.id as call_id,
        d.depth,
        d.op_name,
        f.feedback_type,
        f.payload_dump
    FROM descendants d
    LEFT JOIN feedback f
        ON f.weave_ref = concat('weave:///your-entity/your-project/call/', d.id)  -- REPLACE entity/project
        AND f.project_id = 'your-entity/your-project'  -- REPLACE
)
SELECT
    feedback_type,
    count() as feedback_count,
    round(avg(JSONExtractFloat(payload_dump, 'value')), 3) as avg_score,
    min(JSONExtractFloat(payload_dump, 'value')) as min_score,
    max(JSONExtractFloat(payload_dump, 'value')) as max_score
FROM feedback_data
WHERE feedback_type IS NOT NULL
  AND JSONHas(payload_dump, 'value')
GROUP BY feedback_type
ORDER BY feedback_count DESC;

-- =============================================================================
-- STEP 8: Full aggregation - starting from ANY call (not just root)
-- =============================================================================
-- This lets you aggregate from any node in the tree, not just the root

WITH RECURSIVE
descendants AS (
    -- Base case: start from a specific call (could be mid-tree)
    SELECT
        id,
        parent_id,
        op_name,
        summary_dump,
        started_at,
        ended_at,
        0 AS depth,
        [id] AS path  -- Track path for debugging
    FROM calls_complete
    WHERE project_id = 'your-entity/your-project'  -- REPLACE
      AND id = 'your-call-id'                       -- REPLACE with any call_id

    UNION ALL

    -- Find children
    SELECT
        c.id,
        c.parent_id,
        c.op_name,
        c.summary_dump,
        c.started_at,
        c.ended_at,
        d.depth + 1,
        arrayConcat(d.path, [c.id])  -- Append to path
    FROM calls_complete c
    INNER JOIN descendants d ON c.parent_id = d.id
    WHERE c.project_id = 'your-entity/your-project'  -- REPLACE
      AND d.depth < 50  -- Deeper limit for production
      AND NOT has(d.path, c.id)  -- Cycle detection
)
SELECT
    -- Summary stats
    count() as total_descendants,
    max(depth) as max_depth,

    -- Latency stats
    round(sum(dateDiff('millisecond', started_at, ended_at)) / 1000.0, 2) as total_latency_sec,
    round(avg(dateDiff('millisecond', started_at, ended_at)), 2) as avg_latency_ms,

    -- Count calls with usage data
    countIf(JSONExtractRaw(summary_dump, 'usage') != '{}' AND JSONExtractRaw(summary_dump, 'usage') != '') as calls_with_usage
FROM descendants
WHERE ended_at IS NOT NULL;

-- =============================================================================
-- DIAGNOSTIC: Check if enable_analyzer is on
-- =============================================================================
SELECT name, value
FROM system.settings
WHERE name IN ('enable_analyzer', 'allow_experimental_analyzer');

-- =============================================================================
-- DIAGNOSTIC: Check ClickHouse version (need 24.4+ for recursive CTEs)
-- =============================================================================
SELECT version();
