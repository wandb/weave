"""Query builder for feedback statistics (aggregated payload values over time)."""

from __future__ import annotations

import datetime
import logging
import re
from dataclasses import dataclass

from weave.trace_server.calls_query_builder.stats_query_base import (
    SqlQueryResult,
    StatsQueryBuildResult,
    aggregation_selects_for_metric,
    auto_select_granularity_seconds,
    ensure_max_buckets,
)
from weave.trace_server.calls_query_builder.utils import param_slot, safely_format_sql
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.trace_server_interface import (
    FeedbackMetricSpec,
    FeedbackStatsReq,
)

logger = logging.getLogger(__name__)

# Only allow alphanumeric, underscore, and dot in json_path to prevent SQL injection.
# Also used by feedback_payload_schema.py to filter discovered paths to those safe for
# JSONExtract calls.
JSON_PATH_PATTERN = re.compile(r"^[a-zA-Z0-9_.]+$")


def _validate_and_sanitize_json_path(json_path: str) -> str:
    """Validate json_path contains only safe characters."""
    if not json_path or not json_path.strip():
        raise ValueError("json_path cannot be empty")
    if not JSON_PATH_PATTERN.match(json_path):
        raise ValueError(
            f"json_path may only contain [a-zA-Z0-9_.], got: {json_path!r}"
        )
    return json_path.strip()


def _json_path_args(json_path: str) -> str:
    """Build comma-separated variadic key arguments for a ClickHouse JSON function."""
    _validate_and_sanitize_json_path(json_path)
    return ", ".join(f"'{p}'" for p in json_path.split("."))


def _json_path_to_raw_expr(json_path: str, col: str = "payload_dump") -> str:
    """Build JSONExtractRaw SQL with variadic path args for a dot path."""
    return f"JSONExtractRaw({col}, {_json_path_args(json_path)})"


def _json_path_to_string_expr(json_path: str, col: str = "payload_dump") -> str:
    """Build JSONExtractString SQL with variadic path args for a dot path."""
    return f"JSONExtractString({col}, {_json_path_args(json_path)})"


def _json_path_to_extraction_sql(
    json_path: str,
    value_type: str = "numeric",
    col: str = "payload_dump",
) -> str:
    """Build extraction SQL for a dot path based on value_type.

    Returns:
        SQL expression. Numeric: toFloat64OrNull; boolean: if(raw='true',1,if(raw='false',0,NULL))
        for 0/1/NULL used by count_true/count_false. ClickHouse has no toBoolOrNull.
    """
    raw = _json_path_to_raw_expr(json_path, col)
    if value_type == "numeric":
        return f"toFloat64OrNull({raw})"
    if value_type == "boolean":
        return f"if({raw} = 'true', 1, if({raw} = 'false', 0, NULL))"
    if value_type == "categorical":
        return _json_path_to_string_expr(json_path, col)
    return f"toFloat64OrNull({raw})"


def _json_path_to_metric_slug(json_path: str) -> str:
    """Convert json_path to a safe column alias (e.g. output_score)."""
    _validate_and_sanitize_json_path(json_path)
    return json_path.replace(".", "_").replace(" ", "_")


def trigger_ref_where_clause(trigger_ref: str, pb: ParamBuilder) -> str:
    """Build WHERE clause fragment for trigger_ref.

    Supports exact match or prefix match when trigger_ref ends with ':*'
    (matches all versions of a given monitor).
    """
    if trigger_ref.endswith(":*"):
        prefix = trigger_ref[:-2]
        param = pb.add_param(prefix)
        return f"startsWith(trigger_ref, {param_slot(param, 'String')})"
    param = pb.add_param(trigger_ref)
    return f"trigger_ref = {param_slot(param, 'String')}"


def _normalize_metrics(metrics: list[FeedbackMetricSpec]) -> list[FeedbackMetricSpec]:
    """Filter to metrics that have at least one aggregation or percentile to compute."""
    return [m for m in metrics if m.aggregations or m.percentiles]


@dataclass
class _FeedbackQueryContext:
    """Shared SQL building context used by both bucket and window queries."""

    start: datetime.datetime
    end: datetime.datetime
    start_param: str
    end_param: str
    tz_param: str
    where_sql: str
    main_metrics: list[FeedbackMetricSpec]
    inner_metric_sql: str


def _build_query_context(
    req: FeedbackStatsReq, pb: ParamBuilder
) -> _FeedbackQueryContext:
    """Resolve time range, build shared WHERE clause, and prepare metric expressions.

    Called by both build_feedback_stats_query and build_feedback_stats_window_query
    to avoid duplicating this logic.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    start = req.start
    end = req.end if req.end is not None else now_utc
    tz = req.timezone or "UTC"

    project_param = pb.add_param(req.project_id)
    if start.tzinfo is None:
        start = start.replace(tzinfo=datetime.timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=datetime.timezone.utc)
    start_param = pb.add_param(start.timestamp())
    end_param = pb.add_param(end.timestamp())
    tz_param = pb.add_param(tz)

    where_clauses = [
        f"project_id = {param_slot(project_param, 'String')}",
        f"created_at >= toDateTime({param_slot(start_param, 'Float64')}, {param_slot(tz_param, 'String')})",
        f"created_at < toDateTime({param_slot(end_param, 'Float64')}, {param_slot(tz_param, 'String')})",
    ]
    if req.feedback_type is not None:
        feedback_type_param = pb.add_param(req.feedback_type)
        where_clauses.append(
            f"feedback_type = {param_slot(feedback_type_param, 'String')}"
        )
    if req.trigger_ref is not None:
        where_clauses.append(trigger_ref_where_clause(req.trigger_ref, pb))

    main_metrics = _normalize_metrics(req.metrics)
    inner_metric_exprs = [
        f"{_json_path_to_extraction_sql(spec.json_path, spec.value_type)} AS m_{_json_path_to_metric_slug(spec.json_path)}"
        for spec in main_metrics
    ]

    return _FeedbackQueryContext(
        start=start,
        end=end,
        start_param=start_param,
        end_param=end_param,
        tz_param=tz_param,
        where_sql=" AND ".join(where_clauses),
        main_metrics=main_metrics,
        inner_metric_sql=",\n        ".join(inner_metric_exprs),
    )


def build_feedback_stats_query(
    req: FeedbackStatsReq,
    pb: ParamBuilder,
) -> StatsQueryBuildResult:
    """Generate parameterized ClickHouse SQL for feedback statistics.

    Aggregates numeric/boolean values extracted from payload_dump over time buckets.
    Filters by project_id, created_at range, optional feedback_type and trigger_ref.

    Raises:
        ValueError: If no metrics with aggregations/percentiles are provided.
    """
    if not req.metrics or not _normalize_metrics(req.metrics):
        raise ValueError("At least one metric with aggregations is required")

    ctx = _build_query_context(req, pb)
    time_range_seconds = (ctx.end - ctx.start).total_seconds()
    granularity_seconds = req.granularity or auto_select_granularity_seconds(
        ctx.end - ctx.start
    )
    granularity_seconds = ensure_max_buckets(granularity_seconds, time_range_seconds)
    bucket_interval_param = pb.add_param(granularity_seconds)

    bip = bucket_interval_param
    interval_expr = f"toIntervalSecond({param_slot(bip, 'Int64')})"
    bucket_expr = (
        f"toStartOfInterval(created_at, {interval_expr}, "
        f"{param_slot(ctx.tz_param, 'String')})"
    )

    agg_selects: list[str] = []
    agg_selects_outer: list[str] = []
    columns: list[str] = ["timestamp"]

    for spec in ctx.main_metrics:
        slug = _json_path_to_metric_slug(spec.json_path)
        for select_sql, alias in aggregation_selects_for_metric(
            slug, spec.aggregations or [], spec.percentiles or []
        ):
            agg_selects.append(f"{select_sql} AS {alias}")
            if alias.startswith(("sum_", "count_", "avg_")):
                agg_selects_outer.append(
                    f"COALESCE(aggregated_data.{alias}, 0) AS {alias}"
                )
            else:
                agg_selects_outer.append(f"aggregated_data.{alias} AS {alias}")
            columns.append(alias)

    agg_sql_parts = ["bucket"] + agg_selects + ["count() AS count"]
    agg_sql_for_cte = ",\n          ".join(agg_sql_parts)
    outer_selects = ["all_buckets.bucket AS timestamp"]
    outer_selects.extend(agg_selects_outer)
    outer_selects.append("COALESCE(aggregated_data.count, 0) AS count")
    columns.append("count")
    outer_select_sql = ",\n  ".join(outer_selects)

    sp = ctx.start_param
    ep = ctx.end_param
    tp = ctx.tz_param

    raw_sql = f"""
    WITH
      all_buckets AS (
        SELECT toStartOfInterval(
          toDateTime({param_slot(sp, "Float64")}, {param_slot(tp, "String")}),
          {interval_expr},
          {param_slot(tp, "String")}
        ) + toIntervalSecond(number * {param_slot(bip, "Int64")}) AS bucket
        FROM numbers(
          toUInt64(
            ceil(
              (toUnixTimestamp(toDateTime({param_slot(ep, "Float64")}, {param_slot(tp, "String")})) -
               toUnixTimestamp(toStartOfInterval(toDateTime({param_slot(sp, "Float64")}, {param_slot(tp, "String")}), {interval_expr}, {param_slot(tp, "String")})))
              / {param_slot(bip, "Float64")}
            )
          )
        )
        WHERE bucket < toDateTime({param_slot(ep, "Float64")}, {param_slot(tp, "String")})
      ),
      aggregated_data AS (
        SELECT
          {agg_sql_for_cte}
        FROM
        (
          SELECT
            {bucket_expr} AS bucket,
            {ctx.inner_metric_sql}
          FROM feedback
          WHERE {ctx.where_sql}
        )
        GROUP BY bucket
      )
    SELECT
      {outer_select_sql}
    FROM all_buckets
    LEFT JOIN aggregated_data
      ON all_buckets.bucket = aggregated_data.bucket
    ORDER BY all_buckets.bucket
    """

    return StatsQueryBuildResult(
        sql=safely_format_sql(raw_sql, logger),
        columns=columns,
        parameters=pb.get_params(),
        granularity_seconds=granularity_seconds,
        start=ctx.start,
        end=ctx.end,
    )


def build_feedback_stats_window_query(
    req: FeedbackStatsReq,
    pb: ParamBuilder,
) -> SqlQueryResult | None:
    """Build SQL for window-level aggregations over the full time range.

    Same filters and metrics as the bucket query but without GROUP BY, returning
    a single row with avg, min, max, and percentile values per metric.
    Returns None if there are no metrics or no aggregations to compute.
    """
    if not req.metrics:
        return None

    ctx = _build_query_context(req, pb)

    agg_selects: list[str] = []
    columns: list[str] = []

    for spec in ctx.main_metrics:
        slug = _json_path_to_metric_slug(spec.json_path)
        for select_sql, alias in aggregation_selects_for_metric(
            slug, spec.aggregations or [], spec.percentiles or []
        ):
            agg_selects.append(f"{select_sql} AS {alias}")
            columns.append(alias)

    if not agg_selects:
        return None

    agg_sql = ",\n          ".join(agg_selects)
    raw_sql = f"""
    SELECT
      {agg_sql}
    FROM
    (
      SELECT
        {ctx.inner_metric_sql}
      FROM feedback
      WHERE {ctx.where_sql}
    )
    """

    return SqlQueryResult(
        sql=safely_format_sql(raw_sql, logger),
        columns=columns,
        parameters=pb.get_params(),
    )
