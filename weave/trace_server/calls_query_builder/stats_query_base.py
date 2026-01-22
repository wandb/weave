"""Shared utilities for call statistics query builders.

This module contains common utilities used by both usage_query_builder.py
(token/cost metrics grouped by model) and call_metrics_query_builder.py
(latency/count metrics not grouped by model).
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from weave.trace_server.calls_query_builder.utils import param_slot
from weave.trace_server.orm import ParamBuilder, combine_conditions
from weave.trace_server.trace_server_interface import (
    AggregationType,
    CallsFilter,
)

if TYPE_CHECKING:
    from weave.trace_server.trace_server_interface import CallStatsReq

# Maximum number of buckets to prevent excessive query results
MAX_BUCKETS = 10_000


def auto_select_granularity_seconds(delta: datetime.timedelta) -> int:
    """Automatically select appropriate granularity (in seconds) based on time range span."""
    total_seconds = delta.total_seconds()

    if total_seconds <= 2 * 3600:  # <= 2 hours
        return 300  # 5 minutes
    elif total_seconds <= 12 * 3600:  # <= 12 hours
        return 3600  # 1 hour
    elif total_seconds <= 3 * 86400:  # <= 3 days
        return 6 * 3600  # 6 hours
    elif total_seconds <= 14 * 86400:  # <= 14 days
        return 12 * 3600  # 12 hours
    else:
        return 86400  # 1 day


def ensure_max_buckets(granularity_seconds: int, time_range_seconds: float) -> int:
    """Adjust granularity to ensure we don't exceed MAX_BUCKETS."""
    num_buckets = time_range_seconds / granularity_seconds
    if num_buckets <= MAX_BUCKETS:
        return granularity_seconds

    # Calculate minimum granularity needed to stay under MAX_BUCKETS
    min_granularity = int(time_range_seconds / MAX_BUCKETS) + 1
    return max(granularity_seconds, min_granularity)


def determine_bounds_and_bucket(
    req: CallStatsReq,
) -> tuple[int, datetime.datetime, datetime.datetime, str]:
    """Resolve request parameters to concrete time bounds and bucket configuration.

    Returns:
        - granularity_seconds: bucket size in seconds
        - start: start datetime (UTC)
        - end: end datetime (UTC)
        - bucket_sql_expr: ClickHouse expression for bucketing
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    start = req.start
    end = req.end if req.end is not None else now_utc

    time_range_seconds = (end - start).total_seconds()

    # Determine granularity
    if req.granularity is not None:
        granularity_seconds = req.granularity
    else:
        granularity_seconds = auto_select_granularity_seconds(end - start)

    # Ensure we don't exceed MAX_BUCKETS
    granularity_seconds = ensure_max_buckets(granularity_seconds, time_range_seconds)

    # Build bucket expression using sortable_datetime (always present, unlike started_at on unmerged rows)
    bucket_expr = f"toStartOfInterval(sortable_datetime, INTERVAL {granularity_seconds} SECOND, {{tz}})"

    return granularity_seconds, start, end, bucket_expr


def aggregation_selects_for_metric(
    metric: str,
    aggregations: list[AggregationType],
    percentiles: list[float],
) -> list[tuple[str, str]]:
    """Generate SQL select expressions for the given metric and aggregations.

    Returns a list of (select_expression, column_alias) tuples.
    """
    results: list[tuple[str, str]] = []

    for agg in aggregations:
        col = f"m_{metric}"

        if agg == AggregationType.SUM:
            results.append((f"sumOrNull({col})", f"sum_{metric}"))
        elif agg == AggregationType.AVG:
            results.append((f"avgOrNull({col})", f"avg_{metric}"))
        elif agg == AggregationType.MIN:
            results.append((f"minOrNull({col})", f"min_{metric}"))
        elif agg == AggregationType.MAX:
            results.append((f"maxOrNull({col})", f"max_{metric}"))
        elif agg == AggregationType.COUNT:
            results.append((f"countOrNull({col})", f"count_{metric}"))
        else:
            raise ValueError(f"Unsupported aggregation type: {agg}")

    for p in percentiles:
        if not 0 <= p <= 100:
            raise ValueError(f"Percentile must be between 0 and 100, got {p}")
        col = f"m_{metric}"
        q = round(p / 100.0, 6)
        p_str = str(int(p)) if p == int(p) else str(p)
        alias = f"p{p_str}_{metric}"
        results.append((f"quantileOrNull({q})({col})", alias))

    return results


def build_calls_filter_sql(
    calls_filter: CallsFilter | None,
    pb: ParamBuilder,
) -> str:
    """Build WHERE clause SQL for CallsFilter.

    Generates filter conditions without table alias since this is used
    in an inner subquery that directly queries calls_merged.
    """
    if calls_filter is None:
        return ""

    where_clauses: list[str] = []

    # Handle op_names
    if calls_filter.op_names:
        op_names_param = pb.add_param(calls_filter.op_names)
        where_clauses.append(
            f"op_name IN {param_slot(op_names_param, 'Array(String)')}"
        )

    # Handle trace_roots_only
    if calls_filter.trace_roots_only:
        where_clauses.append("parent_id IS NULL")

    # Handle trace_ids
    if calls_filter.trace_ids:
        trace_ids_param = pb.add_param(calls_filter.trace_ids)
        where_clauses.append(
            f"trace_id IN {param_slot(trace_ids_param, 'Array(String)')}"
        )

    # Handle call_ids
    if calls_filter.call_ids:
        call_ids_param = pb.add_param(calls_filter.call_ids)
        where_clauses.append(f"id IN {param_slot(call_ids_param, 'Array(String)')}")

    # Handle parent_ids
    if calls_filter.parent_ids:
        parent_ids_param = pb.add_param(calls_filter.parent_ids)
        where_clauses.append(
            f"parent_id IN {param_slot(parent_ids_param, 'Array(String)')}"
        )

    # Handle wb_user_ids
    if calls_filter.wb_user_ids:
        wb_user_ids_param = pb.add_param(calls_filter.wb_user_ids)
        where_clauses.append(
            f"wb_user_id IN {param_slot(wb_user_ids_param, 'Array(String)')}"
        )

    # Handle wb_run_ids
    if calls_filter.wb_run_ids:
        wb_run_ids_param = pb.add_param(calls_filter.wb_run_ids)
        where_clauses.append(
            f"wb_run_id IN {param_slot(wb_run_ids_param, 'Array(String)')}"
        )

    if not where_clauses:
        return ""

    return " AND " + combine_conditions(where_clauses, "AND")


def build_grouped_calls_subquery(
    project_param: str,
    start_param: str,
    end_param: str,
    tz_param: str,
    where_filter_sql: str,
    select_columns: list[str],
) -> str:
    """Build SQL for a grouped calls subquery that collapses unmerged call parts.

    Args:
        project_param: Parameter name for the project ID.
        start_param: Parameter name for the start timestamp (epoch seconds).
        end_param: Parameter name for the end timestamp (epoch seconds).
        tz_param: Parameter name for the timezone string.
        where_filter_sql: Additional WHERE filters (should include leading AND).
        select_columns: Column names to aggregate using anyIf for non-null selection.

    Returns:
        SQL string for the grouped calls subquery.

    Examples:
        >>> sql = build_grouped_calls_subquery(
        ...     "pb_0",
        ...     "pb_1",
        ...     "pb_2",
        ...     "pb_3",
        ...     "",
        ...     ["summary_dump"],
        ... )
        >>> "GROUP BY project_id, id" in sql
        True
    """
    if not select_columns:
        raise ValueError("select_columns must include at least one column")

    table_alias = "cm"
    select_sql = ",\n              ".join(
        f"anyIf({table_alias}.{column}, {table_alias}.{column} IS NOT NULL) AS {column}"
        for column in select_columns
    )

    return f"""
        SELECT
              {select_sql}
        FROM calls_merged AS {table_alias}
        WHERE
              {table_alias}.project_id = {param_slot(project_param, "String")}
              AND {table_alias}.sortable_datetime >= toDateTime({param_slot(start_param, "Float64")}, {param_slot(tz_param, "String")})
              AND {table_alias}.sortable_datetime < toDateTime({param_slot(end_param, "Float64")}, {param_slot(tz_param, "String")})
              AND {table_alias}.deleted_at IS NULL{where_filter_sql}
        GROUP BY project_id, id
        """
