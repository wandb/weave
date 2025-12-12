"""
Query builder for trace tree aggregation using recursive CTEs.

This module provides functions to aggregate data (feedback scores, usage metrics, etc.)
across a call tree using ClickHouse's recursive CTE support.

IMPORTANT: Requires ClickHouse 24.4+ with enable_analyzer = 1 setting.
"""

from __future__ import annotations

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.orm import ParamBuilder


def build_trace_tree_aggregate_query(
    req: tsi.TraceTreeAggregateReq,
    pb: ParamBuilder,
) -> tuple[str, list[str]]:
    """Build a recursive CTE query to aggregate feedback across a call tree.

    This query:
    1. Uses a recursive CTE to find all descendants of the specified call
    2. Joins with the feedback table using weave-trace-internal:/// format
    3. Aggregates feedback by type with support for both boolean and numeric values

    Args:
        req: The aggregation request containing project_id, call_id, max_depth
        pb: Parameter builder for safe SQL construction

    Returns:
        Tuple of (SQL query string, list of column names in result)

    Note:
        The query requires `SET enable_analyzer = 1` to be executed before running.
        The caller is responsible for setting this.
    """
    # Add parameters safely
    project_id_param = pb.add_param(req.project_id)
    call_id_param = pb.add_param(req.call_id)
    max_depth_param = pb.add_param(req.max_depth)

    # Build the weave_ref prefix for joining with feedback table
    # Format: weave-trace-internal:///PROJECT_ID/call/
    weave_ref_prefix = f"weave-trace-internal:///{req.project_id}/call/"
    weave_ref_prefix_param = pb.add_param(weave_ref_prefix)

    # Build optional feedback type filter
    feedback_type_filter = ""
    if req.feedback_types:
        feedback_types_param = pb.add_param(req.feedback_types)
        feedback_type_filter = (
            f"AND f.feedback_type IN {{{feedback_types_param}:Array(String)}}"
        )

    query = f"""
WITH RECURSIVE
tree AS (
    -- Base case: start from the specified call
    SELECT
        id,
        parent_id,
        1 AS depth
    FROM calls_merged
    WHERE project_id = {{{project_id_param}:String}}
      AND id = {{{call_id_param}:String}}

    UNION ALL

    -- Recursive case: find all children
    SELECT
        c.id,
        c.parent_id,
        t.depth + 1
    FROM calls_merged c
    INNER JOIN tree t ON c.parent_id = t.id
    WHERE c.project_id = {{{project_id_param}:String}}
      AND t.depth < {{{max_depth_param}:Int32}}
),
-- Summary statistics about the tree
tree_stats AS (
    SELECT
        count() AS total_calls,
        max(depth) AS max_depth_reached
    FROM tree
),
-- Join with feedback and aggregate
feedback_agg AS (
    SELECT
        f.feedback_type,
        count() AS total_count,
        -- Boolean aggregations (for feedback with 'output' boolean field)
        countIf(JSONExtractBool(f.payload_dump, 'output') = true) AS true_count,
        countIf(JSONExtractBool(f.payload_dump, 'output') = false) AS false_count,
        -- Numeric aggregations (for feedback with 'value' numeric field)
        avg(JSONExtractFloat(f.payload_dump, 'value')) AS avg_value,
        min(JSONExtractFloat(f.payload_dump, 'value')) AS min_value,
        max(JSONExtractFloat(f.payload_dump, 'value')) AS max_value,
        sum(JSONExtractFloat(f.payload_dump, 'value')) AS sum_value
    FROM tree t
    INNER JOIN feedback f
        ON f.weave_ref = concat({{{weave_ref_prefix_param}:String}}, t.id)
        AND f.project_id = {{{project_id_param}:String}}
        {feedback_type_filter}
    GROUP BY f.feedback_type
)
SELECT
    ts.total_calls,
    ts.max_depth_reached,
    fa.feedback_type,
    fa.total_count,
    fa.true_count,
    fa.false_count,
    -- Calculate percentage, handling division by zero
    if(fa.total_count > 0,
       round(fa.true_count / fa.total_count * 100, 2),
       NULL) AS true_percentage,
    fa.avg_value,
    fa.min_value,
    fa.max_value,
    fa.sum_value
FROM tree_stats ts
CROSS JOIN feedback_agg fa
ORDER BY fa.total_count DESC
"""

    columns = [
        "total_calls",
        "max_depth_reached",
        "feedback_type",
        "total_count",
        "true_count",
        "false_count",
        "true_percentage",
        "avg_value",
        "min_value",
        "max_value",
        "sum_value",
    ]

    return (query.strip(), columns)


def build_trace_tree_stats_only_query(
    req: tsi.TraceTreeAggregateReq,
    pb: ParamBuilder,
) -> tuple[str, list[str]]:
    """Build a query to get just tree statistics (total calls, max depth).

    Useful when you only need tree structure info without feedback aggregation.

    Args:
        req: The aggregation request
        pb: Parameter builder

    Returns:
        Tuple of (SQL query string, list of column names)
    """
    project_id_param = pb.add_param(req.project_id)
    call_id_param = pb.add_param(req.call_id)
    max_depth_param = pb.add_param(req.max_depth)

    query = f"""
WITH RECURSIVE
tree AS (
    SELECT id, parent_id, 1 AS depth
    FROM calls_merged
    WHERE project_id = {{{project_id_param}:String}}
      AND id = {{{call_id_param}:String}}

    UNION ALL

    SELECT c.id, c.parent_id, t.depth + 1
    FROM calls_merged c
    INNER JOIN tree t ON c.parent_id = t.id
    WHERE c.project_id = {{{project_id_param}:String}}
      AND t.depth < {{{max_depth_param}:Int32}}
)
SELECT
    count() AS total_calls,
    max(depth) AS max_depth_reached
FROM tree
"""

    return (query.strip(), ["total_calls", "max_depth_reached"])


def parse_aggregate_results(
    rows: list[tuple],
    columns: list[str],
) -> tsi.TraceTreeAggregateRes:
    """Parse raw query results into the response model.

    Args:
        rows: Raw result rows from ClickHouse
        columns: Column names corresponding to row positions

    Returns:
        Parsed TraceTreeAggregateRes
    """
    if not rows:
        return tsi.TraceTreeAggregateRes(
            total_calls=0,
            max_depth_reached=0,
            feedback=[],
        )

    # First row contains the tree stats (same across all rows due to CROSS JOIN)
    first_row = dict(zip(columns, rows[0], strict=False))
    total_calls = first_row.get("total_calls", 0)
    max_depth_reached = first_row.get("max_depth_reached", 0)

    # Parse feedback aggregations from each row
    feedback_list: list[tsi.FeedbackAggregation] = []
    for row in rows:
        row_dict = dict(zip(columns, row, strict=False))
        feedback_type = row_dict.get("feedback_type")
        if feedback_type:
            feedback_list.append(
                tsi.FeedbackAggregation(
                    feedback_type=feedback_type,
                    total_count=row_dict.get("total_count", 0),
                    true_count=row_dict.get("true_count"),
                    false_count=row_dict.get("false_count"),
                    true_percentage=row_dict.get("true_percentage"),
                    avg_value=row_dict.get("avg_value"),
                    min_value=row_dict.get("min_value"),
                    max_value=row_dict.get("max_value"),
                    sum_value=row_dict.get("sum_value"),
                )
            )

    return tsi.TraceTreeAggregateRes(
        total_calls=total_calls,
        max_depth_reached=max_depth_reached,
        feedback=feedback_list,
    )
