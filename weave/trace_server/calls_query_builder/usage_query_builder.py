"""Query builder for usage metrics (tokens, costs) grouped by model.

These metrics are grouped by model name since different models have
different token costs and usage patterns.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from weave.trace_server.calls_query_builder.stats_query_base import (
    aggregation_selects_for_metric,
    build_calls_filter_sql,
    build_grouped_calls_subquery,
    determine_bounds_and_bucket,
)
from weave.trace_server.calls_query_builder.utils import param_slot, safely_format_sql
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.trace_server_interface import (
    AggregationType,
    CallStatsReq,
    UsageMetricSpec,
)

logger = logging.getLogger(__name__)


def _normalize_usage_metrics(metrics: list[UsageMetricSpec]) -> list[UsageMetricSpec]:
    """Ensure all usage metrics have at least one aggregation or percentile."""
    normalized: list[UsageMetricSpec] = []
    for spec in metrics:
        aggs = spec.aggregations if spec.aggregations else []
        pcts = spec.percentiles if spec.percentiles else []
        if not aggs and not pcts:
            aggs = [AggregationType.SUM]
        normalized.append(
            UsageMetricSpec(metric=spec.metric, aggregations=aggs, percentiles=pcts)
        )
    return normalized


def _get_usage_metric_extraction_sql(metric: str, json_col: str) -> str:
    """Generate SQL to extract a token usage metric, normalizing provider-specific field names.

    Different LLM providers use different field names for the same concept:
    - OpenAI: prompt_tokens, completion_tokens
    - Anthropic/others: input_tokens, output_tokens

    This function normalizes by summing both variants for input/output tokens.

    Note: Cost metrics (input_cost, output_cost, total_cost) are NOT extracted via SQL.
    They are computed post-query by multiplying token counts by prices from llm_token_prices.

    Args:
        metric: The canonical metric name (input_tokens, output_tokens, total_tokens)
        json_col: The ClickHouse expression for the usage JSON column (e.g., 'kv.2')

    Returns:
        SQL expression that extracts and normalizes the metric value.
    """
    if metric == "input_tokens":
        return f"""(
            ifNull(toFloat64OrNull(JSONExtractRaw({json_col}, 'prompt_tokens')), 0) +
            ifNull(toFloat64OrNull(JSONExtractRaw({json_col}, 'input_tokens')), 0)
        )"""
    elif metric == "output_tokens":
        return f"""(
            ifNull(toFloat64OrNull(JSONExtractRaw({json_col}, 'completion_tokens')), 0) +
            ifNull(toFloat64OrNull(JSONExtractRaw({json_col}, 'output_tokens')), 0)
        )"""
    else:
        return f"toFloat64OrNull(JSONExtractRaw({json_col}, '{metric}'))"


def build_usage_query(
    req: CallStatsReq,
    metrics: list[UsageMetricSpec],
    pb: ParamBuilder,
) -> tuple[
    str,
    list[str],
    dict[str, Any],
    int,
    datetime.datetime,
    datetime.datetime,
]:
    """Generate parameterized ClickHouse SQL for usage metrics (grouped by model).

    Returns (sql, output_columns, parameters, granularity_seconds, start, end).
    """
    granularity_seconds, start, end, bucket_expr = determine_bounds_and_bucket(req)

    project_param = pb.add_param(req.project_id)
    start_epoch = start.replace(tzinfo=datetime.timezone.utc).timestamp()
    end_epoch = end.replace(tzinfo=datetime.timezone.utc).timestamp()
    start_param = pb.add_param(start_epoch)
    end_param = pb.add_param(end_epoch)
    tz_param = pb.add_param(req.timezone or "UTC")
    bucket_interval_param = pb.add_param(granularity_seconds)

    # Build filter clauses - applied directly in WHERE
    where_filter_sql = build_calls_filter_sql(req.filter, pb)

    normalized_metrics = _normalize_usage_metrics(metrics)

    inner_metric_exprs: list[str] = []
    for metric_spec in normalized_metrics:
        metric = metric_spec.metric
        extraction_sql = _get_usage_metric_extraction_sql(metric, "kv.2")
        inner_metric_exprs.append(f"{extraction_sql} AS m_{metric}")

    inner_metric_sql = ""
    if inner_metric_exprs:
        inner_metric_sql = ",\n        " + ",\n        ".join(inner_metric_exprs)

    agg_selects: list[str] = []
    agg_selects_outer: list[str] = []
    columns: list[str] = ["timestamp", "model"]

    for metric_spec in normalized_metrics:
        for select_sql, alias in aggregation_selects_for_metric(
            metric_spec.metric, metric_spec.aggregations, metric_spec.percentiles
        ):
            agg_selects.append(f"{select_sql} AS {alias}")
            # Use COALESCE(0) for SUM/COUNT/AVG (where 0 is sensible default)
            # Keep NULL for MIN/MAX/percentiles (where 0 would be misleading)
            if alias.startswith(("sum_", "count_", "avg_")):
                agg_selects_outer.append(
                    f"COALESCE(aggregated_data.{alias}, 0) AS {alias}"
                )
            else:
                agg_selects_outer.append(f"aggregated_data.{alias} AS {alias}")
            columns.append(alias)

    agg_sql_for_cte = ",\n          ".join(agg_selects)

    outer_selects = ["all_buckets.bucket AS timestamp", "all_models.model"]
    outer_selects.extend(agg_selects_outer)
    outer_selects.append("COALESCE(aggregated_data.count, 0) AS count")
    columns.append("count")

    outer_select_sql = ",\n  ".join(outer_selects)

    # Build bucket expression for all_buckets using seconds interval
    all_buckets_interval = f"INTERVAL {granularity_seconds} SECOND"
    grouped_calls_sql = build_grouped_calls_subquery(
        project_param=project_param,
        start_param=start_param,
        end_param=end_param,
        tz_param=tz_param,
        where_filter_sql=where_filter_sql,
        select_columns=["sortable_datetime", "summary_dump"],
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
              sortable_datetime,
              JSONExtractRaw(ifNull(summary_dump, '{{}}'), 'usage') AS usage_raw
            FROM (
              {grouped_calls_sql}
            )
          )
          ARRAY JOIN JSONExtractKeysAndValuesRaw(ifNull(usage_raw, '{{}}')) AS kv
        )
        GROUP BY bucket, model
      ),
      all_models AS (
        SELECT DISTINCT model FROM aggregated_data
      )
    SELECT
      {outer_select_sql}
    FROM all_buckets
    CROSS JOIN all_models
    LEFT JOIN aggregated_data
      ON all_buckets.bucket = aggregated_data.bucket
      AND all_models.model = aggregated_data.model
    ORDER BY all_buckets.bucket, all_models.model
    """

    return (
        safely_format_sql(raw_sql, logger),
        columns,
        pb.get_params(),
        granularity_seconds,
        start,
        end,
    )
