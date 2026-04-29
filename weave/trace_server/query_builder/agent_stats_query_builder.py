"""Stats query builder for GenAI agent spans.

The public shape mirrors the agent span query layer: callers can filter with
the Mongo-style ``Query`` DSL and group by span columns or typed custom
attribute maps. Unlike ``/agents/spans/query``, callers choose the metric
bundle so the response can directly power charts.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Any

from weave.trace_server.agents import semconv
from weave.trace_server.agents.constants import OP_INVOKE_AGENT
from weave.trace_server.agents.types import (
    AgentGroupByRef,
    AgentSpanStatsAggregation,
    AgentSpanStatsColumn,
    AgentSpanStatsColumnValueType,
    AgentSpanStatsMetricSpec,
    AgentSpanStatsReq,
    AgentSpanStatsValueType,
)
from weave.trace_server.calls_query_builder.stats_query_base import (
    auto_select_granularity_seconds,
    ensure_max_buckets,
)
from weave.trace_server.calls_query_builder.utils import param_slot, safely_format_sql
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_query_builder import (
    add_time_filters,
    resolve_group_by,
)
from weave.trace_server.query_builder.agent_query_compiler import compile_agent_query

logger = logging.getLogger(__name__)

_CUSTOM_ATTR_VALUE_TYPES: dict[str, AgentSpanStatsValueType] = {
    "custom_attrs_string": "string",
    "custom_attrs_int": "number",
    "custom_attrs_float": "number",
    "custom_attrs_bool": "boolean",
}

_COLUMN_VALUE_TYPES: dict[str, AgentSpanStatsValueType] = {
    # string columns
    "operation_name": "string",
    "provider_name": "string",
    "agent_name": "string",
    "agent_id": "string",
    "agent_description": "string",
    "agent_version": "string",
    "request_model": "string",
    "response_model": "string",
    "response_id": "string",
    "conversation_id": "string",
    "conversation_name": "string",
    "tool_name": "string",
    "tool_type": "string",
    "tool_call_id": "string",
    "tool_description": "string",
    "tool_call_arguments": "string",
    "tool_call_result": "string",
    "reasoning_content": "string",
    "output_type": "string",
    "error_type": "string",
    "server_address": "string",
    "compaction_summary": "string",
    "trace_id": "string",
    "span_id": "string",
    "parent_span_id": "string",
    "span_name": "string",
    "span_kind": "string",
    "status_code": "string",
    "status_message": "string",
    "wb_user_id": "string",
    "wb_run_id": "string",
    # numeric columns
    "input_tokens": "number",
    "output_tokens": "number",
    "reasoning_tokens": "number",
    "cache_creation_input_tokens": "number",
    "cache_read_input_tokens": "number",
    "request_temperature": "number",
    "request_max_tokens": "number",
    "request_top_p": "number",
    "request_frequency_penalty": "number",
    "request_presence_penalty": "number",
    "request_seed": "number",
    "request_choice_count": "number",
    "server_port": "number",
    "compaction_items_before": "number",
    "compaction_items_after": "number",
    "wb_run_step": "number",
    "wb_run_step_end": "number",
}

_DERIVED_VALUE_TYPES: dict[str, AgentSpanStatsValueType] = {
    "duration_ms": "number",
    "total_tokens": "number",
    "is_error": "boolean",
    "is_invocation": "boolean",
}


@dataclass(frozen=True, slots=True)
class AgentSpanStatsQueryBuildResult:
    """Parameterized SQL and response metadata for an agent span stats query."""

    sql: str
    columns: list[str]
    column_metadata: list[AgentSpanStatsColumn]
    parameters: dict[str, Any]
    granularity_seconds: int
    start: datetime.datetime
    end: datetime.datetime


@dataclass(frozen=True, slots=True)
class _MetricSQL:
    value_sql: str
    valid_sql: str
    value_type: AgentSpanStatsValueType


def build_agent_span_stats_query(
    req: AgentSpanStatsReq,
    pb: ParamBuilder,
) -> AgentSpanStatsQueryBuildResult:
    """Build a chart-ready aggregation query for agent spans."""
    start, end = _resolve_time_bounds(req)
    granularity_seconds = _resolve_granularity(req, start, end)
    tz = req.timezone or "UTC"

    where = _spans_where(pb, req, start, end)
    group_refs = req.group_by or []
    resolved_groups = resolve_group_by(pb, group_refs) if group_refs else []

    metric_exprs: list[str] = []
    agg_selects: list[str] = []
    outer_metric_selects: list[str] = []
    columns: list[str] = ["timestamp"]
    column_metadata: list[AgentSpanStatsColumn] = [
        AgentSpanStatsColumn(
            name="timestamp",
            role="time",
            value_type="datetime",
        )
    ]

    for group_ref in group_refs:
        alias = group_ref.alias or group_ref.key
        columns.append(alias)
        column_metadata.append(
            AgentSpanStatsColumn(
                name=alias,
                role="group",
                value_type=_group_value_type(group_ref),
            )
        )

    for metric in req.metrics:
        metric_sql = _metric_sql(metric, pb)
        metric_exprs.append(f"{metric_sql.value_sql} AS m_{metric.alias}")
        metric_exprs.append(f"toUInt8({metric_sql.valid_sql}) AS v_{metric.alias}")
        for select_sql, output_name in _aggregation_selects(metric):
            agg_selects.append(f"{select_sql} AS {output_name}")
            outer_metric_selects.append(
                f"{_outer_metric_expr(output_name)} AS {output_name}"
            )
            columns.append(output_name)
            column_metadata.append(
                AgentSpanStatsColumn(
                    name=output_name,
                    role="metric",
                    value_type="number",
                    metric=metric.alias,
                    aggregation=_aggregation_label(output_name, metric.alias),
                )
            )

    if not agg_selects:
        raise ValueError("at least one aggregation or percentile is required")
    if len(set(columns)) != len(columns):
        raise ValueError("duplicate output columns")

    start_epoch = start.replace(tzinfo=datetime.timezone.utc).timestamp()
    end_epoch = end.replace(tzinfo=datetime.timezone.utc).timestamp()
    start_param = pb.add_param(start_epoch)
    end_param = pb.add_param(end_epoch)
    tz_param = pb.add_param(tz)
    bucket_interval_param = pb.add_param(granularity_seconds)
    group_limit_slot = pb.add(req.group_limit, param_type="UInt64")

    raw_sql = _build_grouped_query(
        where=where,
        group_refs=group_refs,
        resolved_groups=resolved_groups,
        metric_exprs=metric_exprs,
        agg_selects=agg_selects,
        outer_metric_selects=outer_metric_selects,
        start_param=start_param,
        end_param=end_param,
        tz_param=tz_param,
        bucket_interval_param=bucket_interval_param,
        granularity_seconds=granularity_seconds,
        group_limit_slot=group_limit_slot,
    )

    return AgentSpanStatsQueryBuildResult(
        sql=safely_format_sql(raw_sql, logger),
        columns=columns,
        column_metadata=column_metadata,
        parameters=pb.get_params(),
        granularity_seconds=granularity_seconds,
        start=start,
        end=end,
    )


def _resolve_time_bounds(
    req: AgentSpanStatsReq,
) -> tuple[datetime.datetime, datetime.datetime]:
    start = _as_utc(req.start)
    end = (
        _as_utc(req.end)
        if req.end is not None
        else datetime.datetime.now(datetime.timezone.utc)
    )
    return start, end


def _as_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def _resolve_granularity(
    req: AgentSpanStatsReq,
    start: datetime.datetime,
    end: datetime.datetime,
) -> int:
    range_seconds = (end - start).total_seconds()
    granularity = req.granularity or auto_select_granularity_seconds(end - start)
    return ensure_max_buckets(granularity, range_seconds)


def _spans_where(
    pb: ParamBuilder,
    req: AgentSpanStatsReq,
    start: datetime.datetime,
    end: datetime.datetime,
) -> str:
    pid_slot = pb.add(req.project_id, param_type="String")
    conditions = [f"s.project_id = {pid_slot}"]
    add_time_filters(
        conditions,
        pb,
        started_after=start,
        started_before=end,
    )
    if req.query is not None:
        conditions.append(compile_agent_query(req.query, pb))
    return " AND ".join(conditions)


def _metric_sql(metric: AgentSpanStatsMetricSpec, pb: ParamBuilder) -> _MetricSQL:
    if metric.derived is not None:
        value_type = _DERIVED_VALUE_TYPES[metric.derived]
        if metric.value_type != value_type:
            raise ValueError(
                f"metric {metric.alias!r} declares {metric.value_type!r}, "
                f"but derived metric {metric.derived!r} is {value_type!r}"
            )
        return _derived_metric_sql(metric.derived, pb)

    if metric.field is None:
        raise ValueError(f"metric {metric.alias!r} must set field or derived")

    ref = metric.field
    if ref.source == "field":
        col = semconv.FILTERABLE_KEY_TO_COLUMN.get(ref.key, ref.key)
        column_value_type = _COLUMN_VALUE_TYPES.get(col)
        if column_value_type is None:
            raise ValueError(f"field {ref.key!r} is not stat-aggregatable")
        if metric.value_type != column_value_type:
            raise ValueError(
                f"field {ref.key!r} has value_type {column_value_type!r}, "
                f"got {metric.value_type!r}"
            )
        value_sql = f"s.{col}"
        if column_value_type == "number":
            value_sql = f"toFloat64({value_sql})"
        return _MetricSQL(
            value_sql=value_sql,
            valid_sql="1",
            value_type=column_value_type,
        )

    value_type = _CUSTOM_ATTR_VALUE_TYPES[ref.source]
    if metric.value_type != value_type:
        raise ValueError(
            f"{ref.source} values have value_type {value_type!r}, "
            f"got {metric.value_type!r}"
        )
    key_slot = pb.add(str(ref.key), param_type="String")
    value_sql = f"s.{ref.source}[{key_slot}]"
    if value_type == "number":
        value_sql = f"toFloat64({value_sql})"
    return _MetricSQL(
        value_sql=value_sql,
        valid_sql=f"mapContains(s.{ref.source}, {key_slot})",
        value_type=value_type,
    )


def _derived_metric_sql(metric: str, pb: ParamBuilder) -> _MetricSQL:
    if metric == "duration_ms":
        duration = (
            "toFloat64(toUnixTimestamp64Milli(s.ended_at) - "
            "toUnixTimestamp64Milli(s.started_at))"
        )
        return _MetricSQL(
            value_sql=f"if(s.ended_at > s.started_at, {duration}, NULL)",
            valid_sql="s.ended_at > s.started_at",
            value_type="number",
        )
    if metric == "total_tokens":
        return _MetricSQL(
            value_sql="toFloat64(s.input_tokens + s.output_tokens)",
            valid_sql="1",
            value_type="number",
        )
    if metric == "is_error":
        return _MetricSQL(
            value_sql="s.status_code = 'ERROR'",
            valid_sql="1",
            value_type="boolean",
        )
    if metric == "is_invocation":
        op_slot = pb.add(OP_INVOKE_AGENT, param_type="String")
        return _MetricSQL(
            value_sql=f"s.operation_name = {op_slot}",
            valid_sql="1",
            value_type="boolean",
        )
    raise ValueError(f"unknown derived metric: {metric!r}")


def _aggregation_selects(
    metric: AgentSpanStatsMetricSpec,
) -> list[tuple[str, str]]:
    metric_col = f"m_{metric.alias}"
    valid_col = f"v_{metric.alias}"
    results: list[tuple[str, str]] = []

    for agg in metric.aggregations:
        output_name = _output_name(agg, metric.alias)
        if agg == "sum":
            results.append(
                (f"sumOrNull(if({valid_col}, {metric_col}, NULL))", output_name)
            )
        elif agg == "avg":
            results.append(
                (f"avgOrNull(if({valid_col}, {metric_col}, NULL))", output_name)
            )
        elif agg == "min":
            results.append(
                (f"minOrNull(if({valid_col}, {metric_col}, NULL))", output_name)
            )
        elif agg == "max":
            results.append(
                (f"maxOrNull(if({valid_col}, {metric_col}, NULL))", output_name)
            )
        elif agg == "count":
            results.append((f"countIf({valid_col})", output_name))
        elif agg == "count_distinct":
            results.append((f"uniqExactIf({metric_col}, {valid_col})", output_name))
        elif agg == "count_true":
            results.append((f"countIf({valid_col} AND {metric_col} = 1)", output_name))
        elif agg == "count_false":
            results.append((f"countIf({valid_col} AND {metric_col} = 0)", output_name))
        else:
            raise ValueError(f"unsupported aggregation: {agg!r}")

    for p in metric.percentiles:
        q = round(p / 100.0, 6)
        p_str = str(int(p)) if p == int(p) else str(p).replace(".", "_")
        output_name = f"p{p_str}_{metric.alias}"
        results.append(
            (
                f"quantileOrNull({q})(if({valid_col}, {metric_col}, NULL))",
                output_name,
            )
        )

    return results


def _output_name(agg: AgentSpanStatsAggregation, alias: str) -> str:
    return f"{agg}_{alias}"


def _outer_metric_expr(output_name: str) -> str:
    if output_name.startswith(
        ("sum_", "avg_", "count_", "count_distinct_", "count_true_", "count_false_")
    ):
        return f"COALESCE(aggregated_data.{output_name}, 0)"
    return f"aggregated_data.{output_name}"


def _aggregation_label(output_name: str, metric_alias: str) -> str:
    suffix = f"_{metric_alias}"
    if output_name.endswith(suffix):
        return output_name[: -len(suffix)]
    return output_name


def _group_value_type(group_ref: AgentGroupByRef) -> AgentSpanStatsColumnValueType:
    if group_ref.source in _CUSTOM_ATTR_VALUE_TYPES:
        return _CUSTOM_ATTR_VALUE_TYPES[group_ref.source]
    return _COLUMN_VALUE_TYPES.get(group_ref.key, "string")


def _build_grouped_query(
    *,
    where: str,
    group_refs: list[AgentGroupByRef],
    resolved_groups: list[tuple[str, str]],
    metric_exprs: list[str],
    agg_selects: list[str],
    outer_metric_selects: list[str],
    start_param: str,
    end_param: str,
    tz_param: str,
    bucket_interval_param: str,
    granularity_seconds: int,
    group_limit_slot: str,
) -> str:
    all_buckets_sql = _all_buckets_sql(
        start_param,
        end_param,
        tz_param,
        bucket_interval_param,
        granularity_seconds,
    )
    bucket_expr = (
        f"toStartOfInterval(s.started_at, INTERVAL {granularity_seconds} SECOND, "
        f"{param_slot(tz_param, 'String')})"
    )
    metric_select_sql = ",\n            ".join(metric_exprs)
    agg_select_sql = ",\n          ".join(agg_selects)
    outer_metric_sql = ",\n  ".join(outer_metric_selects)

    if not group_refs:
        return f"""
        WITH
          all_buckets AS (
            {all_buckets_sql}
          ),
          filtered_spans AS (
            SELECT *
            FROM spans s
            WHERE {where}
          ),
          aggregated_data AS (
            SELECT
              bucket,
              {agg_select_sql}
            FROM (
              SELECT
                {bucket_expr} AS bucket,
                {metric_select_sql}
              FROM filtered_spans s
            )
            GROUP BY bucket
          )
        SELECT
          all_buckets.bucket AS timestamp,
          {outer_metric_sql}
        FROM all_buckets
        LEFT JOIN aggregated_data
          ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY timestamp
        """

    select_group_cols = ", ".join(
        f"{expr} AS {alias}" for expr, alias in resolved_groups
    )
    group_aliases = [alias for _, alias in resolved_groups]
    group_by_clause = ", ".join(group_aliases)
    outer_group_select_sql = ", ".join(
        f"top_groups.{alias} AS {alias}" for alias in group_aliases
    )
    inner_group_select_sql = ",\n                ".join(
        f"{expr} AS {alias}" for expr, alias in resolved_groups
    )
    group_join_sql = " AND ".join(
        f"top_groups.{alias} = aggregated_data.{alias}" for alias in group_aliases
    )
    order_group_sql = ", ".join(group_aliases)
    return f"""
    WITH
      all_buckets AS (
        {all_buckets_sql}
      ),
      filtered_spans AS (
        SELECT *
        FROM spans s
        WHERE {where}
      ),
      top_groups AS (
        SELECT {select_group_cols}
        FROM filtered_spans s
        GROUP BY {group_by_clause}
        ORDER BY count() DESC
        LIMIT {group_limit_slot}
      ),
      aggregated_data AS (
        SELECT
          bucket,
          {group_by_clause},
          {agg_select_sql}
        FROM (
          SELECT
            {bucket_expr} AS bucket,
            {inner_group_select_sql},
            {metric_select_sql}
          FROM filtered_spans s
        )
        GROUP BY bucket, {group_by_clause}
      )
    SELECT
      all_buckets.bucket AS timestamp,
      {outer_group_select_sql},
      {outer_metric_sql}
    FROM all_buckets
    CROSS JOIN top_groups
    LEFT JOIN aggregated_data
      ON all_buckets.bucket = aggregated_data.bucket
      AND {group_join_sql}
    ORDER BY timestamp, {order_group_sql}
    """


def _all_buckets_sql(
    start_param: str,
    end_param: str,
    tz_param: str,
    bucket_interval_param: str,
    granularity_seconds: int,
) -> str:
    all_buckets_interval = f"INTERVAL {granularity_seconds} SECOND"
    start_slot = param_slot(start_param, "Float64")
    end_slot = param_slot(end_param, "Float64")
    tz_slot = param_slot(tz_param, "String")
    interval_int_slot = param_slot(bucket_interval_param, "Int64")
    interval_float_slot = param_slot(bucket_interval_param, "Float64")
    return f"""
    SELECT toStartOfInterval(
      toDateTime({start_slot}, {tz_slot}),
      {all_buckets_interval},
      {tz_slot}
    ) + toIntervalSecond(number * {interval_int_slot}) AS bucket
    FROM numbers(
      toUInt64(
        ceil(
          (toUnixTimestamp(toDateTime({end_slot}, {tz_slot})) -
           toUnixTimestamp(toStartOfInterval(
             toDateTime({start_slot}, {tz_slot}),
             {all_buckets_interval},
             {tz_slot}
           )))
          / {interval_float_slot}
        )
      )
    )
    WHERE bucket < toDateTime({end_slot}, {tz_slot})
    """
