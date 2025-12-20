from __future__ import annotations

import datetime
import logging
from collections.abc import Iterable
from typing import Any

from weave.trace_server.calls_query_builder.utils import param_slot, safely_format_sql
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.trace_server_interface import (
    UsageAggregation,
    UsageAnalyticsReq,
    UsageBinPreset,
)

logger = logging.getLogger(__name__)


def _determine_bounds_and_bucket(
    req: UsageAnalyticsReq,
) -> tuple[str, datetime.datetime, datetime.datetime, str]:
    """Returns a tuple of:
    - bucket_size_str (human readable, e.g. '12h', '1h', '5m')
    - start (UTC)
    - end (UTC)
    - bucket_sql_expr: ClickHouse expression for bucketing (alias is applied by caller)
    """
    tz = req.timezone or "UTC"
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    start = req.time.start
    end = req.time.end
    preset = req.time.preset

    if preset is not None:
        if preset == UsageBinPreset.last_7d:
            end = now_utc
            start = end - datetime.timedelta(days=7)
            bucket_size = "12h"
            bucket_expr = "toStartOfInterval(ifNull(started_at, sortable_datetime), INTERVAL 12 HOUR, {tz})"
        elif preset == UsageBinPreset.last_24h:
            end = now_utc
            start = end - datetime.timedelta(hours=24)
            bucket_size = "1h"
            bucket_expr = "toStartOfInterval(ifNull(started_at, sortable_datetime), INTERVAL 1 HOUR, {tz})"
        elif preset == UsageBinPreset.last_1h:
            end = now_utc
            start = end - datetime.timedelta(hours=1)
            bucket_size = "5m"
            bucket_expr = "toStartOfInterval(ifNull(started_at, sortable_datetime), INTERVAL 5 MINUTE, {tz})"
        else:
            raise ValueError(f"Unsupported preset: {preset}")
    else:
        if start is None or end is None:
            raise ValueError("Explicit time range requires both start and end")
        delta = end - start
        if delta >= datetime.timedelta(days=2):
            bucket_size = "12h"
            bucket_expr = "toStartOfInterval(ifNull(started_at, sortable_datetime), INTERVAL 12 HOUR, {tz})"
        elif delta >= datetime.timedelta(hours=12):
            bucket_size = "1h"
            bucket_expr = "toStartOfInterval(ifNull(started_at, sortable_datetime), INTERVAL 1 HOUR, {tz})"
        else:
            bucket_size = "5m"
            bucket_expr = "toStartOfInterval(ifNull(started_at, sortable_datetime), INTERVAL 5 MINUTE, {tz})"

    if start is None or end is None:
        raise ValueError("Start and end must be computed")
    return bucket_size, start, end, bucket_expr


def _aggregation_selects_for_metric(
    metric: str, aggs: Iterable[UsageAggregation]
) -> list[tuple[str, str]]:
    """Builds a list of (select_sql, alias) tuples for a single metric
    given the requested aggregations.

    Special case: 'requests' is treated as a count of calls, not a metric to extract.
    """
    selects: list[tuple[str, str]] = []

    # Special handling for 'requests' - it's a count, not a metric
    if metric == "requests":
        for agg in aggs:
            # For requests, both sum and avg should just return the count
            if agg.type == "avg":
                selects.append(("count()", f"avg_{metric}"))
            elif agg.type == "sum":
                selects.append(("count()", f"sum_{metric}"))
            elif agg.type == "quantile":
                # Quantile doesn't make sense for request counts, but we'll allow it
                # by treating it as the count value
                quantiles: list[float] = []
                if agg.q is not None:
                    quantiles.append(agg.q)
                if agg.qs:
                    quantiles.extend(agg.qs)
                if not quantiles:
                    raise ValueError("quantile aggregation requires q or qs")
                for q in quantiles:
                    pct = round(q * 100)
                    selects.append(("count()", f"p{pct}_{metric}"))
            else:
                raise ValueError(f"Unsupported aggregation type: {agg.type}")
        return selects

    # Normal metric handling
    col_expr = f"m_{metric}"
    for agg in aggs:
        if agg.type == "avg":
            selects.append((f"avg({col_expr})", f"avg_{metric}"))
        elif agg.type == "sum":
            selects.append((f"sum({col_expr})", f"sum_{metric}"))
        elif agg.type == "quantile":
            qs: list[float] = []
            if agg.q is not None:
                qs.append(agg.q)
            if agg.qs:
                qs.extend(agg.qs)
            if not qs:
                raise ValueError("quantile aggregation requires q or qs")
            for q in qs:
                # p95 formatting etc.
                pct = round(q * 100)
                selects.append((f"quantile({q})({col_expr})", f"p{pct}_{metric}"))
        else:
            raise ValueError(f"Unsupported aggregation type: {agg.type}")
    return selects


def _get_bucket_interval_seconds(bucket_size: str) -> int:
    """Convert bucket size string to seconds."""
    if bucket_size == "12h":
        return 12 * 60 * 60
    elif bucket_size == "1h":
        return 60 * 60
    elif bucket_size == "5m":
        return 5 * 60
    else:
        raise ValueError(f"Unsupported bucket size: {bucket_size}")


def build_usage_analytics_query(
    req: UsageAnalyticsReq, pb: ParamBuilder
) -> tuple[str, list[str], dict[str, Any], str]:
    """Generate parameterized ClickHouse SQL for usage analytics.
    Returns (sql, output_columns, parameters, bucket_size_str)

    This query generates all expected time buckets and fills in missing data with zeros.
    """
    bucket_size, start, end, bucket_expr = _determine_bounds_and_bucket(req)

    # Parameters
    project_param = pb.add_param(req.project_id)
    # Convert datetimes to epoch seconds (Float64) to align with global parameter processing
    start_epoch = start.replace(tzinfo=datetime.timezone.utc).timestamp()
    end_epoch = end.replace(tzinfo=datetime.timezone.utc).timestamp()
    start_param = pb.add_param(start_epoch)
    end_param = pb.add_param(end_epoch)
    tz_param = pb.add_param(req.timezone or "UTC")

    # Bucket interval in seconds for generating all expected buckets
    bucket_interval_seconds = _get_bucket_interval_seconds(bucket_size)
    bucket_interval_param = pb.add_param(bucket_interval_seconds)

    # Optional op_name LIKE
    op_like_clause = ""
    if req.filter and req.filter.op_name_like:
        op_like_param = pb.add_param(req.filter.op_name_like)
        op_like_clause = f"AND op_name LIKE {param_slot(op_like_param, 'String')}"

    # Build metric projections in inner select
    # Skip 'requests' since it's just a count, not extracted from JSON
    inner_metric_exprs: list[str] = []
    metric_names: list[str] = []
    for metric_spec in req.metrics:
        metric = metric_spec.metric
        metric_names.append(metric)
        # Skip 'requests' - it's handled as count() in aggregations
        if metric != "requests":
            inner_metric_exprs.append(
                f"toFloat64OrNull(JSONExtractRaw(kv.2, {param_slot(pb.add_param(metric), 'String')})) AS m_{metric}"
            )

    inner_metric_sql = ""
    if inner_metric_exprs:
        inner_metric_sql = ",\n        " + ",\n        ".join(inner_metric_exprs)

    # Build aggregation selects for both the CTE and final select
    agg_selects = []
    agg_selects_with_coalesce = []
    for metric_spec in req.metrics:
        for select_sql, alias in _aggregation_selects_for_metric(
            metric_spec.metric, metric_spec.aggregations
        ):
            agg_selects.append(f"{select_sql} AS {alias}")
            # Wrap aggregations in COALESCE to return 0 for missing data in final select
            agg_selects_with_coalesce.append(
                f"COALESCE(aggregated_data.{alias}, 0) AS {alias}"
            )

    agg_sql_for_cte = ",\n          ".join(agg_selects)

    # Build outer aggregations with COALESCE for missing values
    outer_selects = ["all_buckets.bucket", "all_models.model"]
    outer_selects.extend(agg_selects_with_coalesce)
    outer_selects.append("COALESCE(aggregated_data.count, 0) AS count")

    outer_select_sql = ",\n  ".join(outer_selects)

    # Final SQL with generated buckets and cross join with models
    raw_sql = f"""
    WITH
      -- Generate all expected time buckets
      all_buckets AS (
        SELECT toDateTime(
          toUnixTimestamp(toDateTime({param_slot(start_param, "Float64")}, {param_slot(tz_param, "String")})) + (number * {param_slot(bucket_interval_param, "Int64")}),
          {param_slot(tz_param, "String")}
        ) AS bucket
        FROM numbers(
          toUInt64(
            ceil(
              (toUnixTimestamp(toDateTime({param_slot(end_param, "Float64")}, {param_slot(tz_param, "String")})) -
               toUnixTimestamp(toDateTime({param_slot(start_param, "Float64")}, {param_slot(tz_param, "String")})))
              / {param_slot(bucket_interval_param, "Float64")}
            )
          )
        )
        WHERE bucket < toDateTime({param_slot(end_param, "Float64")}, {param_slot(tz_param, "String")})
      ),
      -- Get all distinct models from actual data
      all_models AS (
        SELECT DISTINCT kv.1 AS model
        FROM
        (
          SELECT
            JSONExtractRaw(ifNull(summary_dump, '{{}}'), 'usage') AS usage_raw
          FROM calls_merged
          WHERE
            project_id = {param_slot(project_param, "String")}
            AND calls_merged.sortable_datetime >= toDateTime({param_slot(start_param, "Float64")}, {param_slot(tz_param, "String")})
            AND calls_merged.sortable_datetime <  toDateTime({param_slot(end_param, "Float64")}, {param_slot(tz_param, "String")})
            {op_like_clause}
        )
        ARRAY JOIN JSONExtractKeysAndValuesRaw(ifNull(usage_raw, '{{}}')) AS kv
        WHERE kv.1 != ''
      ),
      -- Aggregate actual data
      aggregated_data AS (
        SELECT
          bucket,
          model,
          {agg_sql_for_cte},
          count() AS count
        FROM
        (
          SELECT
            {bucket_expr.format(tz=param_slot(tz_param, "String"))} AS bucket,
            kv.1 AS model{inner_metric_sql}
          FROM
          (
            SELECT
              started_at,
              calls_merged.sortable_datetime,
              op_name,
              JSONExtractRaw(ifNull(summary_dump, '{{}}'), 'usage') AS usage_raw
            FROM calls_merged
            WHERE
              project_id = {param_slot(project_param, "String")}
              AND calls_merged.sortable_datetime >= toDateTime({param_slot(start_param, "Float64")}, {param_slot(tz_param, "String")})
              AND calls_merged.sortable_datetime <  toDateTime({param_slot(end_param, "Float64")}, {param_slot(tz_param, "String")})
              {op_like_clause}
          )
          ARRAY JOIN JSONExtractKeysAndValuesRaw(ifNull(usage_raw, '{{}}')) AS kv
        )
        GROUP BY bucket, model
      )
    -- Cross join all buckets with all models, then left join actual data
    SELECT
      {outer_select_sql}
    FROM all_buckets
    CROSS JOIN all_models
    LEFT JOIN aggregated_data
      ON all_buckets.bucket = aggregated_data.bucket
      AND all_models.model = aggregated_data.model
    ORDER BY all_buckets.bucket, all_models.model
    """

    # Build columns in the exact same order as the outer SELECT.
    # This must stay in lockstep with agg_selects_with_coalesce above; otherwise
    # values will be zipped to the wrong column names when mapping result_rows.
    columns: list[str] = ["bucket", "model"]
    for metric_spec in req.metrics:
        metric = metric_spec.metric
        for agg in metric_spec.aggregations:
            if agg.type == "avg":
                columns.append(f"avg_{metric}")
            elif agg.type == "sum":
                columns.append(f"sum_{metric}")
            elif agg.type == "quantile":
                quantiles: list[float] = []
                if agg.q is not None:
                    quantiles.append(agg.q)
                if agg.qs:
                    quantiles.extend(agg.qs)
                if not quantiles:
                    raise ValueError("quantile aggregation requires q or qs")
                for q in quantiles:
                    pct = round(q * 100)
                    columns.append(f"p{pct}_{metric}")
            else:
                raise ValueError(f"Unsupported aggregation type: {agg.type}")

    columns.append("count")

    return safely_format_sql(raw_sql, logger), columns, pb.get_params(), bucket_size
