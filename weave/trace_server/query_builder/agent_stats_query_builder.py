"""Stats query builder for GenAI agent spans.

This module turns an AgentSpanStatsReq into one parameterized ClickHouse query
plus the metadata needed to decode its tabular response. The request mirrors
the agent span list API: callers can reuse the same Query filter tree, group by
span columns or typed custom attributes, and choose the metric bundle needed by
their charts.
"""

from __future__ import annotations

import datetime
import logging
import math
from dataclasses import dataclass
from typing import Any

from weave.trace_server.agents import semconv
from weave.trace_server.agents.constants import (
    MAX_AGENT_STATS_RESULT_ROWS,
    OP_INVOKE_AGENT,
)
from weave.trace_server.agents.types import (
    AGENT_SPAN_STATS_DERIVED_VALUE_TYPES,
    AgentGroupByRef,
    AgentSpanStatsAggregation,
    AgentSpanStatsColumn,
    AgentSpanStatsColumnValueType,
    AgentSpanStatsDerivedMetric,
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

_VALUE_TYPE_STRING: AgentSpanStatsValueType = "string"
_VALUE_TYPE_NUMBER: AgentSpanStatsValueType = "number"
_VALUE_TYPE_BOOLEAN: AgentSpanStatsValueType = "boolean"
_VALUE_TYPE_DATETIME: AgentSpanStatsColumnValueType = "datetime"

_SOURCE_FIELD = "field"
_SOURCE_CUSTOM_ATTRS_STRING = "custom_attrs_string"
_SOURCE_CUSTOM_ATTRS_INT = "custom_attrs_int"
_SOURCE_CUSTOM_ATTRS_FLOAT = "custom_attrs_float"
_SOURCE_CUSTOM_ATTRS_BOOL = "custom_attrs_bool"

_SPANS_TABLE = "spans"
_SPAN_ALIAS = "s"
_RESPONSE_TIMESTAMP_COLUMN = "timestamp"
_BUCKET_COLUMN = "bucket"
_CTE_ALL_BUCKETS = "all_buckets"
_CTE_FILTERED_SPANS = "filtered_spans"
_CTE_AGGREGATED_DATA = "aggregated_data"
_CTE_TOP_GROUPS = "top_groups"

_COL_PROJECT_ID = "project_id"
_COL_STARTED_AT = "started_at"
_COL_ENDED_AT = "ended_at"
_COL_STATUS_CODE = "status_code"
_COL_INPUT_TOKENS = semconv.CANONICAL_KEY_TO_COLUMN[semconv.USAGE_INPUT_TOKENS.key]
_COL_OUTPUT_TOKENS = semconv.CANONICAL_KEY_TO_COLUMN[semconv.USAGE_OUTPUT_TOKENS.key]
_COL_OPERATION_NAME = semconv.CANONICAL_KEY_TO_COLUMN[semconv.OPERATION_NAME.key]

_STATUS_CODE_ERROR = "ERROR"
_DERIVED_DURATION_MS: AgentSpanStatsDerivedMetric = "duration_ms"
_DERIVED_TOTAL_TOKENS: AgentSpanStatsDerivedMetric = "total_tokens"
_DERIVED_IS_ERROR: AgentSpanStatsDerivedMetric = "is_error"
_DERIVED_IS_INVOCATION: AgentSpanStatsDerivedMetric = "is_invocation"

_AGG_SUM: AgentSpanStatsAggregation = "sum"
_AGG_AVG: AgentSpanStatsAggregation = "avg"
_AGG_MIN: AgentSpanStatsAggregation = "min"
_AGG_MAX: AgentSpanStatsAggregation = "max"
_AGG_COUNT: AgentSpanStatsAggregation = "count"
_AGG_COUNT_DISTINCT: AgentSpanStatsAggregation = "count_distinct"
_AGG_COUNT_TRUE: AgentSpanStatsAggregation = "count_true"
_AGG_COUNT_FALSE: AgentSpanStatsAggregation = "count_false"
_ZERO_FILL_AGGREGATIONS: frozenset[AgentSpanStatsAggregation] = frozenset(
    {
        _AGG_SUM,
        _AGG_COUNT,
        _AGG_COUNT_DISTINCT,
        _AGG_COUNT_TRUE,
        _AGG_COUNT_FALSE,
    }
)

_CUSTOM_ATTR_VALUE_TYPES: dict[str, AgentSpanStatsValueType] = {
    _SOURCE_CUSTOM_ATTRS_STRING: _VALUE_TYPE_STRING,
    _SOURCE_CUSTOM_ATTRS_INT: _VALUE_TYPE_NUMBER,
    _SOURCE_CUSTOM_ATTRS_FLOAT: _VALUE_TYPE_NUMBER,
    _SOURCE_CUSTOM_ATTRS_BOOL: _VALUE_TYPE_BOOLEAN,
}

_CORE_SPAN_VALUE_TYPES: dict[str, AgentSpanStatsValueType] = {
    "trace_id": _VALUE_TYPE_STRING,
    "span_id": _VALUE_TYPE_STRING,
    "parent_span_id": _VALUE_TYPE_STRING,
    "span_name": _VALUE_TYPE_STRING,
    "span_kind": _VALUE_TYPE_STRING,
    _COL_STATUS_CODE: _VALUE_TYPE_STRING,
    "status_message": _VALUE_TYPE_STRING,
    "wb_user_id": _VALUE_TYPE_STRING,
    "wb_run_id": _VALUE_TYPE_STRING,
    "wb_run_step": _VALUE_TYPE_NUMBER,
    "wb_run_step_end": _VALUE_TYPE_NUMBER,
}

_SEMCONV_TYPE_TO_STATS_TYPE: dict[str, AgentSpanStatsValueType] = {
    "string": _VALUE_TYPE_STRING,
    "json": _VALUE_TYPE_STRING,
    "string[]": _VALUE_TYPE_STRING,
    "int": _VALUE_TYPE_NUMBER,
    "float": _VALUE_TYPE_NUMBER,
}

_COLUMN_VALUE_TYPES: dict[str, AgentSpanStatsValueType] = {
    **{
        column: _SEMCONV_TYPE_TO_STATS_TYPE[semconv.ATTRIBUTES[key].type]
        for key, column in semconv.CANONICAL_KEY_TO_COLUMN.items()
    },
    **_CORE_SPAN_VALUE_TYPES,
}


def _span_col(column: str) -> str:
    return f"{_SPAN_ALIAS}.{column}"


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


@dataclass(frozen=True, slots=True)
class _MetricOutput:
    """One aggregate column produced for a requested metric."""

    name: str
    metric_alias: str
    aggregation_label: str
    aggregate_sql: str
    outer_sql: str


@dataclass(frozen=True, slots=True)
class _MetricPlan:
    """SQL fragments needed to extract and aggregate one requested metric."""

    expressions: list[str]
    outputs: list[_MetricOutput]


@dataclass(frozen=True, slots=True)
class _StatsQuerySQLParts:
    """Common SQL fragments shared by grouped and ungrouped stats queries."""

    all_buckets_sql: str
    bucket_expr: str
    metric_select_sql: str
    agg_select_sql: str
    outer_metric_sql: str


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

    metric_plans = [_metric_plan(metric, pb) for metric in req.metrics]
    metric_exprs = [expr for plan in metric_plans for expr in plan.expressions]
    metric_outputs = [output for plan in metric_plans for output in plan.outputs]
    columns, column_metadata = _response_columns(group_refs, metric_outputs)

    if not metric_outputs:
        raise ValueError("at least one aggregation or percentile is required")
    if len(set(columns)) != len(columns):
        raise ValueError("duplicate output columns")

    agg_selects = [
        f"{output.aggregate_sql} AS {output.name}" for output in metric_outputs
    ]
    outer_metric_selects = [
        f"{output.outer_sql} AS {output.name}" for output in metric_outputs
    ]

    start_epoch = start.replace(tzinfo=datetime.timezone.utc).timestamp()
    end_epoch = end.replace(tzinfo=datetime.timezone.utc).timestamp()
    start_param = pb.add_param(start_epoch)
    end_param = pb.add_param(end_epoch)
    tz_param = pb.add_param(tz)
    bucket_interval_param = pb.add_param(granularity_seconds)
    group_limit_slot = None
    if resolved_groups:
        group_limit = _effective_group_limit(req, start, end, granularity_seconds)
        group_limit_slot = pb.add(group_limit, param_type="UInt64")

    raw_sql = _build_stats_query(
        where=where,
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
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
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


def _effective_group_limit(
    req: AgentSpanStatsReq,
    start: datetime.datetime,
    end: datetime.datetime,
    granularity_seconds: int,
) -> int:
    if not req.group_by:
        return req.group_limit

    bucket_count = _estimated_bucket_count(start, end, granularity_seconds)
    max_groups = max(1, MAX_AGENT_STATS_RESULT_ROWS // bucket_count)
    return min(req.group_limit, max_groups)


def _estimated_bucket_count(
    start: datetime.datetime,
    end: datetime.datetime,
    granularity_seconds: int,
) -> int:
    range_seconds = max(0.0, (end - start).total_seconds())
    return max(1, math.ceil(range_seconds / granularity_seconds) + 1)


def _spans_where(
    pb: ParamBuilder,
    req: AgentSpanStatsReq,
    start: datetime.datetime,
    end: datetime.datetime,
) -> str:
    pid_slot = pb.add(req.project_id, param_type="String")
    conditions = [f"{_span_col(_COL_PROJECT_ID)} = {pid_slot}"]
    add_time_filters(
        conditions,
        pb,
        started_after=start,
        started_before=end,
    )
    if req.query is not None:
        conditions.append(compile_agent_query(req.query, pb))
    return " AND ".join(conditions)


def _response_columns(
    group_refs: list[AgentGroupByRef],
    metric_outputs: list[_MetricOutput],
) -> tuple[list[str], list[AgentSpanStatsColumn]]:
    """Build the response column order and matching column metadata."""
    columns = [_RESPONSE_TIMESTAMP_COLUMN]
    metadata = [
        AgentSpanStatsColumn(
            name=_RESPONSE_TIMESTAMP_COLUMN,
            role="time",
            value_type=_VALUE_TYPE_DATETIME,
        )
    ]

    for group_ref in group_refs:
        alias = group_ref.alias or group_ref.key
        columns.append(alias)
        metadata.append(
            AgentSpanStatsColumn(
                name=alias,
                role="group",
                value_type=_group_value_type(group_ref),
            )
        )

    for output in metric_outputs:
        columns.append(output.name)
        metadata.append(
            AgentSpanStatsColumn(
                name=output.name,
                role="metric",
                value_type=_VALUE_TYPE_NUMBER,
                metric=output.metric_alias,
                aggregation=output.aggregation_label,
            )
        )

    return columns, metadata


def _metric_plan(metric: AgentSpanStatsMetricSpec, pb: ParamBuilder) -> _MetricPlan:
    """Resolve a request metric into span-level expressions and output columns."""
    metric_sql = _metric_sql(metric, pb)
    metric_col = f"m_{metric.alias}"
    valid_col = f"v_{metric.alias}"
    return _MetricPlan(
        expressions=[
            f"{metric_sql.value_sql} AS {metric_col}",
            f"toUInt8({metric_sql.valid_sql}) AS {valid_col}",
        ],
        outputs=_metric_outputs(metric, metric_col, valid_col),
    )


def _metric_sql(metric: AgentSpanStatsMetricSpec, pb: ParamBuilder) -> _MetricSQL:
    """Return the per-span value expression and validity guard for a metric."""
    if metric.derived is not None:
        value_type = AGENT_SPAN_STATS_DERIVED_VALUE_TYPES[metric.derived]
        if metric.value_type != value_type:
            raise ValueError(
                f"metric {metric.alias!r} declares {metric.value_type!r}, "
                f"but derived metric {metric.derived!r} is {value_type!r}"
            )
        return _derived_metric_sql(metric.derived, pb)

    if metric.field is None:
        raise ValueError(f"metric {metric.alias!r} must set field or derived")

    ref = metric.field
    if ref.source == _SOURCE_FIELD:
        col = semconv.FILTERABLE_KEY_TO_COLUMN.get(ref.key, ref.key)
        column_value_type = _COLUMN_VALUE_TYPES.get(col)
        if column_value_type is None:
            raise ValueError(f"field {ref.key!r} is not stat-aggregatable")
        if metric.value_type != column_value_type:
            raise ValueError(
                f"field {ref.key!r} has value_type {column_value_type!r}, "
                f"got {metric.value_type!r}"
            )
        value_sql = _span_col(col)
        if column_value_type == _VALUE_TYPE_NUMBER:
            value_sql = f"toFloat64({value_sql})"
        return _MetricSQL(
            value_sql=value_sql,
            valid_sql="1",
        )

    value_type = _CUSTOM_ATTR_VALUE_TYPES[ref.source]
    if metric.value_type != value_type:
        raise ValueError(
            f"{ref.source} values have value_type {value_type!r}, "
            f"got {metric.value_type!r}"
        )
    key_slot = pb.add(str(ref.key), param_type="String")
    source_column = _span_col(ref.source)
    value_sql = f"{source_column}[{key_slot}]"
    if value_type == _VALUE_TYPE_NUMBER:
        value_sql = f"toFloat64({value_sql})"
    return _MetricSQL(
        value_sql=value_sql,
        valid_sql=f"mapContains({source_column}, {key_slot})",
    )


def _derived_metric_sql(
    metric: AgentSpanStatsDerivedMetric,
    pb: ParamBuilder,
) -> _MetricSQL:
    if metric == _DERIVED_DURATION_MS:
        started_at = _span_col(_COL_STARTED_AT)
        ended_at = _span_col(_COL_ENDED_AT)
        duration = (
            f"toFloat64(toUnixTimestamp64Milli({ended_at}) - "
            f"toUnixTimestamp64Milli({started_at}))"
        )
        return _MetricSQL(
            value_sql=f"if({ended_at} > {started_at}, {duration}, NULL)",
            valid_sql=f"{ended_at} > {started_at}",
        )
    if metric == _DERIVED_TOTAL_TOKENS:
        return _MetricSQL(
            value_sql=(
                f"toFloat64({_span_col(_COL_INPUT_TOKENS)} + "
                f"{_span_col(_COL_OUTPUT_TOKENS)})"
            ),
            valid_sql="1",
        )
    if metric == _DERIVED_IS_ERROR:
        return _MetricSQL(
            value_sql=f"{_span_col(_COL_STATUS_CODE)} = '{_STATUS_CODE_ERROR}'",
            valid_sql="1",
        )
    if metric == _DERIVED_IS_INVOCATION:
        op_slot = pb.add(OP_INVOKE_AGENT, param_type="String")
        return _MetricSQL(
            value_sql=f"{_span_col(_COL_OPERATION_NAME)} = {op_slot}",
            valid_sql="1",
        )
    raise ValueError(f"unknown derived metric: {metric!r}")


def _metric_outputs(
    metric: AgentSpanStatsMetricSpec,
    metric_col: str,
    valid_col: str,
) -> list[_MetricOutput]:
    """Build all aggregate output columns requested for one metric."""
    outputs: list[_MetricOutput] = []

    for agg in metric.aggregations:
        outputs.append(_aggregation_output(metric.alias, agg, metric_col, valid_col))

    for p in metric.percentiles:
        q = round(p / 100.0, 6)
        label = _percentile_label(p)
        outputs.append(
            _metric_output(
                name=f"{label}_{metric.alias}",
                metric_alias=metric.alias,
                aggregation_label=label,
                aggregate_sql=(
                    f"quantileOrNull({q})(if({valid_col}, {metric_col}, NULL))"
                ),
                coalesce_empty=False,
            )
        )

    return outputs


def _aggregation_output(
    metric_alias: str,
    agg: AgentSpanStatsAggregation,
    metric_col: str,
    valid_col: str,
) -> _MetricOutput:
    name = _output_name(agg, metric_alias)
    coalesce_empty = agg in _ZERO_FILL_AGGREGATIONS

    if agg == _AGG_SUM:
        aggregate_sql = f"sumOrNull(if({valid_col}, {metric_col}, NULL))"
    elif agg == _AGG_AVG:
        aggregate_sql = f"avgOrNull(if({valid_col}, {metric_col}, NULL))"
    elif agg == _AGG_MIN:
        aggregate_sql = f"minOrNull(if({valid_col}, {metric_col}, NULL))"
    elif agg == _AGG_MAX:
        aggregate_sql = f"maxOrNull(if({valid_col}, {metric_col}, NULL))"
    elif agg == _AGG_COUNT:
        aggregate_sql = f"countIf({valid_col})"
    elif agg == _AGG_COUNT_DISTINCT:
        aggregate_sql = f"uniqExactIf({metric_col}, {valid_col})"
    elif agg == _AGG_COUNT_TRUE:
        aggregate_sql = f"countIf({valid_col} AND {metric_col} = 1)"
    elif agg == _AGG_COUNT_FALSE:
        aggregate_sql = f"countIf({valid_col} AND {metric_col} = 0)"
    else:
        raise ValueError(f"unsupported aggregation: {agg!r}")

    return _metric_output(
        name=name,
        metric_alias=metric_alias,
        aggregation_label=agg,
        aggregate_sql=aggregate_sql,
        coalesce_empty=coalesce_empty,
    )


def _metric_output(
    *,
    name: str,
    metric_alias: str,
    aggregation_label: str,
    aggregate_sql: str,
    coalesce_empty: bool,
) -> _MetricOutput:
    raw_outer_sql = f"{_CTE_AGGREGATED_DATA}.{name}"
    outer_sql = f"COALESCE({raw_outer_sql}, 0)" if coalesce_empty else raw_outer_sql
    return _MetricOutput(
        name=name,
        metric_alias=metric_alias,
        aggregation_label=aggregation_label,
        aggregate_sql=aggregate_sql,
        outer_sql=outer_sql,
    )


def _output_name(agg: AgentSpanStatsAggregation, alias: str) -> str:
    return f"{agg}_{alias}"


def _percentile_label(percentile: float) -> str:
    percentile_str = (
        str(int(percentile))
        if percentile == int(percentile)
        else str(percentile).replace(".", "_")
    )
    return f"p{percentile_str}"


def _group_value_type(group_ref: AgentGroupByRef) -> AgentSpanStatsColumnValueType:
    if group_ref.source in _CUSTOM_ATTR_VALUE_TYPES:
        return _CUSTOM_ATTR_VALUE_TYPES[group_ref.source]
    return _COLUMN_VALUE_TYPES.get(group_ref.key, _VALUE_TYPE_STRING)


def _build_stats_query(
    *,
    where: str,
    resolved_groups: list[tuple[str, str]],
    metric_exprs: list[str],
    agg_selects: list[str],
    outer_metric_selects: list[str],
    start_param: str,
    end_param: str,
    tz_param: str,
    bucket_interval_param: str,
    granularity_seconds: int,
    group_limit_slot: str | None,
) -> str:
    """Render the appropriate SQL shape for grouped or ungrouped stats."""
    parts = _stats_query_sql_parts(
        metric_exprs=metric_exprs,
        agg_selects=agg_selects,
        outer_metric_selects=outer_metric_selects,
        start_param=start_param,
        end_param=end_param,
        tz_param=tz_param,
        bucket_interval_param=bucket_interval_param,
        granularity_seconds=granularity_seconds,
    )

    if not resolved_groups:
        return _build_ungrouped_stats_query(where=where, parts=parts)

    assert group_limit_slot is not None
    return _build_grouped_stats_query(
        where=where,
        resolved_groups=resolved_groups,
        group_limit_slot=group_limit_slot,
        parts=parts,
    )


def _stats_query_sql_parts(
    *,
    metric_exprs: list[str],
    agg_selects: list[str],
    outer_metric_selects: list[str],
    start_param: str,
    end_param: str,
    tz_param: str,
    bucket_interval_param: str,
    granularity_seconds: int,
) -> _StatsQuerySQLParts:
    """Build SQL fragments shared by every stats query shape."""
    bucket_expr = (
        f"toStartOfInterval({_span_col(_COL_STARTED_AT)}, "
        f"INTERVAL {granularity_seconds} SECOND, "
        f"{param_slot(tz_param, 'String')})"
    )
    return _StatsQuerySQLParts(
        all_buckets_sql=_all_buckets_sql(
            start_param,
            end_param,
            tz_param,
            bucket_interval_param,
            granularity_seconds,
        ),
        bucket_expr=bucket_expr,
        metric_select_sql=",\n            ".join(metric_exprs),
        agg_select_sql=",\n          ".join(agg_selects),
        outer_metric_sql=",\n  ".join(outer_metric_selects),
    )


def _build_ungrouped_stats_query(
    *,
    where: str,
    parts: _StatsQuerySQLParts,
) -> str:
    """Render one row per time bucket for the full filtered span set."""
    return f"""
    WITH
      {_CTE_ALL_BUCKETS} AS (
        {parts.all_buckets_sql}
      ),
      {_CTE_FILTERED_SPANS} AS (
        SELECT *
        FROM {_SPANS_TABLE} {_SPAN_ALIAS}
        WHERE {where}
      ),
      {_CTE_AGGREGATED_DATA} AS (
        SELECT
          {_BUCKET_COLUMN},
          {parts.agg_select_sql}
        FROM (
          SELECT
            {parts.bucket_expr} AS {_BUCKET_COLUMN},
            {parts.metric_select_sql}
          FROM {_CTE_FILTERED_SPANS} {_SPAN_ALIAS}
        )
        GROUP BY {_BUCKET_COLUMN}
      )
    SELECT
      {_CTE_ALL_BUCKETS}.{_BUCKET_COLUMN} AS {_RESPONSE_TIMESTAMP_COLUMN},
      {parts.outer_metric_sql}
    FROM {_CTE_ALL_BUCKETS}
    LEFT JOIN {_CTE_AGGREGATED_DATA}
      ON {_CTE_ALL_BUCKETS}.{_BUCKET_COLUMN} = {_CTE_AGGREGATED_DATA}.{_BUCKET_COLUMN}
    ORDER BY {_RESPONSE_TIMESTAMP_COLUMN}
    """


def _build_grouped_stats_query(
    *,
    where: str,
    resolved_groups: list[tuple[str, str]],
    group_limit_slot: str,
    parts: _StatsQuerySQLParts,
) -> str:
    """Render one row per time bucket and selected top group."""
    select_group_cols = ", ".join(
        f"{expr} AS {alias}" for expr, alias in resolved_groups
    )
    group_aliases = [alias for _, alias in resolved_groups]
    group_by_clause = ", ".join(group_aliases)
    outer_group_select_sql = ", ".join(
        f"{_CTE_TOP_GROUPS}.{alias} AS {alias}" for alias in group_aliases
    )
    inner_group_select_sql = ",\n                ".join(
        f"{expr} AS {alias}" for expr, alias in resolved_groups
    )
    group_join_sql = " AND ".join(
        f"{_CTE_TOP_GROUPS}.{alias} = {_CTE_AGGREGATED_DATA}.{alias}"
        for alias in group_aliases
    )
    order_group_sql = ", ".join(group_aliases)
    return f"""
    WITH
      {_CTE_ALL_BUCKETS} AS (
        {parts.all_buckets_sql}
      ),
      {_CTE_FILTERED_SPANS} AS (
        SELECT *
        FROM {_SPANS_TABLE} {_SPAN_ALIAS}
        WHERE {where}
      ),
      {_CTE_TOP_GROUPS} AS (
        SELECT {select_group_cols}
        FROM {_CTE_FILTERED_SPANS} {_SPAN_ALIAS}
        GROUP BY {group_by_clause}
        ORDER BY count() DESC
        LIMIT {group_limit_slot}
      ),
      {_CTE_AGGREGATED_DATA} AS (
        SELECT
          {_BUCKET_COLUMN},
          {group_by_clause},
          {parts.agg_select_sql}
        FROM (
          SELECT
            {parts.bucket_expr} AS {_BUCKET_COLUMN},
            {inner_group_select_sql},
            {parts.metric_select_sql}
          FROM {_CTE_FILTERED_SPANS} {_SPAN_ALIAS}
        )
        GROUP BY {_BUCKET_COLUMN}, {group_by_clause}
      )
    SELECT
      {_CTE_ALL_BUCKETS}.{_BUCKET_COLUMN} AS {_RESPONSE_TIMESTAMP_COLUMN},
      {outer_group_select_sql},
      {parts.outer_metric_sql}
    FROM {_CTE_ALL_BUCKETS}
    CROSS JOIN {_CTE_TOP_GROUPS}
    LEFT JOIN {_CTE_AGGREGATED_DATA}
      ON {_CTE_ALL_BUCKETS}.{_BUCKET_COLUMN} = {_CTE_AGGREGATED_DATA}.{_BUCKET_COLUMN}
      AND {group_join_sql}
    ORDER BY {_RESPONSE_TIMESTAMP_COLUMN}, {order_group_sql}
    """


def _all_buckets_sql(
    start_param: str,
    end_param: str,
    tz_param: str,
    bucket_interval_param: str,
    granularity_seconds: int,
) -> str:
    """Render the synthetic bucket table used to fill empty time buckets."""
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
    ) + toIntervalSecond(number * {interval_int_slot}) AS {_BUCKET_COLUMN}
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
    WHERE {_BUCKET_COLUMN} < toDateTime({end_slot}, {tz_slot})
    """
