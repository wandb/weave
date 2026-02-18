"""Query builder for call-level metrics (latency, call count, error count).

These metrics are NOT grouped by model - they aggregate across all calls
matching the filter criteria.
"""

from __future__ import annotations

import datetime
import logging

from weave.trace_server.calls_query_builder.stats_query_base import (
    StatsQueryBuildResult,
    aggregation_selects_for_metric,
    build_calls_filter_sql,
    build_grouped_calls_subquery,
    determine_bounds_and_bucket,
)
from weave.trace_server.calls_query_builder.utils import param_slot, safely_format_sql
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable, TableConfig
from weave.trace_server.trace_server_interface import (
    AggregationType,
    CallMetricSpec,
    CallStatsReq,
)

logger = logging.getLogger(__name__)


def _normalize_call_metrics(metrics: list[CallMetricSpec]) -> list[CallMetricSpec]:
    """Ensure all call metrics have at least one aggregation or percentile."""
    normalized: list[CallMetricSpec] = []
    for spec in metrics:
        aggs = spec.aggregations if spec.aggregations else []
        pcts = spec.percentiles if spec.percentiles else []
        if not aggs and not pcts:
            aggs = [AggregationType.SUM]
        normalized.append(
            CallMetricSpec(metric=spec.metric, aggregations=aggs, percentiles=pcts)
        )
    return normalized


def _get_call_metric_extraction_sql(
    metric: str, read_table: ReadTable = ReadTable.CALLS_MERGED
) -> str:
    """Generate SQL to extract a call-level metric.

    Args:
        metric: The metric name (latency_ms, call_count, error_count)
        read_table: Which table to query; affects NULL vs sentinel checks.

    Returns:
        SQL expression that extracts the metric value.
    """
    if metric == "latency_ms":
        return "dateDiff('millisecond', started_at, ended_at)"
    elif metric == "call_count":
        return "1"
    elif metric == "error_count":
        if read_table != ReadTable.CALLS_MERGED:
            return "if(exception != '', 1, 0)"
        return "if(exception IS NOT NULL, 1, 0)"
    else:
        raise ValueError(f"Unknown call metric: {metric}")


def build_call_metrics_query(
    req: CallStatsReq,
    metrics: list[CallMetricSpec],
    pb: ParamBuilder,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
) -> StatsQueryBuildResult:
    """Generate parameterized ClickHouse SQL for call-level metrics (not grouped by model).

    Args:
        req: The CallStatsReq containing time range and filter settings.
        metrics: Call metrics to compute (latency_ms, call_count, error_count).
        pb: ParamBuilder for parameterized queries.
        read_table: Which table to query (calls_merged or calls_complete).

    Returns:
        Named query build result with SQL, output columns, params, and time bounds.
    """
    time_bounds = determine_bounds_and_bucket(req, read_table)
    granularity_seconds = time_bounds.granularity_seconds

    project_param = pb.add_param(req.project_id)
    start_epoch = time_bounds.start.replace(tzinfo=datetime.timezone.utc).timestamp()
    end_epoch = time_bounds.end.replace(tzinfo=datetime.timezone.utc).timestamp()
    start_param = pb.add_param(start_epoch)
    end_param = pb.add_param(end_epoch)
    tz_param = pb.add_param(req.timezone or "UTC")
    bucket_interval_param = pb.add_param(granularity_seconds)

    where_filter_sql = build_calls_filter_sql(req.filter, pb)

    normalized_metrics = _normalize_call_metrics(metrics)

    inner_metric_exprs: list[str] = []
    for metric_spec in normalized_metrics:
        metric = metric_spec.metric
        extraction_sql = _get_call_metric_extraction_sql(metric, read_table)
        inner_metric_exprs.append(f"{extraction_sql} AS m_{metric}")

    inner_metric_sql = ",\n        ".join(inner_metric_exprs)

    agg_selects: list[str] = []
    agg_selects_outer: list[str] = []
    columns: list[str] = ["timestamp"]

    for metric_spec in normalized_metrics:
        for select_sql, alias in aggregation_selects_for_metric(
            metric_spec.metric, metric_spec.aggregations, metric_spec.percentiles
        ):
            agg_selects.append(f"{select_sql} AS {alias}")
            if alias.startswith(("sum_", "count_", "avg_")):
                agg_selects_outer.append(
                    f"COALESCE(aggregated_data.{alias}, 0) AS {alias}"
                )
            else:
                agg_selects_outer.append(f"aggregated_data.{alias} AS {alias}")
            columns.append(alias)

    agg_sql_for_cte = ",\n          ".join(agg_selects)

    outer_selects = ["all_buckets.bucket AS timestamp"]
    outer_selects.extend(agg_selects_outer)
    outer_selects.append("COALESCE(aggregated_data.count, 0) AS count")
    columns.append("count")

    outer_select_sql = ",\n  ".join(outer_selects)

    all_buckets_interval = f"INTERVAL {granularity_seconds} SECOND"

    # Select the appropriate datetime field based on the table
    table_config = TableConfig.from_read_table(read_table)
    datetime_field = table_config.datetime_filter_field
    grouped_calls_sql = build_grouped_calls_subquery(
        project_param=project_param,
        start_param=start_param,
        end_param=end_param,
        tz_param=tz_param,
        where_filter_sql=where_filter_sql,
        select_columns=[datetime_field, "started_at", "ended_at", "exception"],
        read_table=read_table,
    )

    raw_sql = f"""
    WITH
      all_buckets AS (
        SELECT toStartOfInterval(
          toDateTime({param_slot(start_param, "Float64")}, {param_slot(tz_param, "String")}),
          {all_buckets_interval},
          {param_slot(tz_param, "String")}
        ) + toIntervalSecond(number * {param_slot(bucket_interval_param, "Int64")}) AS bucket
        FROM numbers(
          toUInt64(
            ceil(
              (toUnixTimestamp(toDateTime({param_slot(end_param, "Float64")}, {param_slot(tz_param, "String")})) -
               toUnixTimestamp(toStartOfInterval(toDateTime({param_slot(start_param, "Float64")}, {param_slot(tz_param, "String")}), {all_buckets_interval}, {param_slot(tz_param, "String")})))
              / {param_slot(bucket_interval_param, "Float64")}
            )
          )
        )
        WHERE bucket < toDateTime({param_slot(end_param, "Float64")}, {param_slot(tz_param, "String")})
      ),
      aggregated_data AS (
        SELECT
          bucket,
          {agg_sql_for_cte},
          count() AS count
        FROM
        (
          SELECT
            {time_bounds.bucket_expr.format(tz=param_slot(tz_param, "String"))} AS bucket,
            {inner_metric_sql}
          FROM (
            {grouped_calls_sql}
          )
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
        start=time_bounds.start,
        end=time_bounds.end,
    )
