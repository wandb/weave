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
from weave.trace_server.agents.constants import MAX_AGENT_STATS_RESULT_ROWS
from weave.trace_server.agents.span_costs import (
    COST_DERIVED_METRIC_NAMES,
    cost_augmented_source_sql,
)
from weave.trace_server.agents.types import (
    AgentGroupByRef,
    AgentSpanGroupFilter,
    AgentSpanStatsAggregation,
    AgentSpanStatsColumn,
    AgentSpanStatsColumnValueType,
    AgentSpanStatsMetricSpec,
    AgentSpanStatsNumericBucketSpec,
    AgentSpanStatsReq,
    AgentSpanStatsValueType,
    group_by_ref_alias,
)
from weave.trace_server.calls_query_builder.stats_query_base import (
    auto_select_granularity_seconds,
    ensure_max_buckets,
)
from weave.trace_server.calls_query_builder.utils import param_slot, safely_format_sql
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder import agent_trace_attribution
from weave.trace_server.query_builder.agent_query_builder import (
    _FIELD_GROUP_BY_SOURCES,
    _project_filter_sql,
    add_time_filters,
    ensure_group_filters_match,
    group_filters_having_sql,
    resolve_agent_span_field_column,
    resolve_group_by,
    span_group_filters,
    span_measure_sql,
    span_value_sql,
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
_RESPONSE_BUCKET_INDEX_COLUMN = "bucket_index"
_RESPONSE_BUCKET_MIN_COLUMN = "bucket_min"
_RESPONSE_BUCKET_MAX_COLUMN = "bucket_max"
_BUCKET_COLUMN = "bucket"
_CTE_ALL_BUCKETS = "all_buckets"
_CTE_FILTERED_SPANS = "filtered_spans"
_CTE_FILTERED_METRIC_SPANS = "filtered_metric_spans"
_CTE_QUALIFIED_CONVERSATIONS = "qualified_conversations"
_CTE_VALUE_ROWS = "value_rows"
_BOUNDS_TUPLE = "bounds_tuple"
_CTE_AGGREGATED_DATA = "aggregated_data"
_CTE_TOP_GROUPS = "top_groups"

_COL_PROJECT_ID = "project_id"
_COL_STARTED_AT = "started_at"
_COL_ENDED_AT = "ended_at"
_COL_STATUS_CODE = "status_code"
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


def _value_ref_is_cost(value: Any) -> bool:
    return (
        value is not None
        and getattr(value, "source", None) == "derived"
        and getattr(value, "key", None) in COST_DERIVED_METRIC_NAMES
    )


def _stats_requires_costs(req: AgentSpanStatsReq) -> bool:
    """Whether any value ref in the request reads a cost column.

    Scans metrics, numeric-bucket value/measure, and group-filter measures so
    the query reads from the cost-augmented span source iff cost is needed —
    avoiding the price JOIN on the common no-cost path.
    """
    if any(_value_ref_is_cost(metric.value) for metric in req.metrics):
        return True
    bucket = req.bucket_by
    if isinstance(bucket, AgentSpanStatsNumericBucketSpec):
        if _value_ref_is_cost(bucket.value):
            return True
        if bucket.measure is not None and _value_ref_is_cost(bucket.measure.value):
            return True
    return any(
        _value_ref_is_cost(group_filter.measure.value)
        for group_filter in req.group_filters
    )


def _conversation_group_by() -> list[AgentGroupByRef]:
    return [AgentGroupByRef(source="column", key="conversation_id")]


@dataclass(frozen=True, slots=True)
class AgentSpanStatsQueryBuildResult:
    """Parameterized SQL and response metadata for an agent span stats query."""

    sql: str
    columns: list[str]
    column_metadata: list[AgentSpanStatsColumn]
    parameters: dict[str, Any]
    granularity_seconds: int | None
    start: datetime.datetime
    end: datetime.datetime
    bucket_type: str


@dataclass(frozen=True, slots=True)
class _MetricSQL:
    value_sql: str
    valid_sql: str
    value_type: AgentSpanStatsColumnValueType


@dataclass(frozen=True, slots=True)
class _MetricOutput:
    """One aggregate column produced for a requested metric."""

    name: str
    metric_alias: str
    aggregation_label: str
    aggregate_sql: str
    outer_sql: str
    value_type: AgentSpanStatsColumnValueType


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


@dataclass(frozen=True, slots=True)
class _SpanSourceFilterSQL:
    """WHERE filters and FROM source for direct reads from the spans table.

    `source` is the raw `spans` table, or an attributed-spans subquery when the
    request filters/groups/aggregates on an identity column that inherits from
    its trace (see `agent_trace_attribution`).
    """

    where: str
    source: str = _SPANS_TABLE

    @property
    def clause(self) -> str:
        return f"WHERE {self.where}"


def build_agent_span_stats_query(
    req: AgentSpanStatsReq,
    pb: ParamBuilder,
) -> AgentSpanStatsQueryBuildResult:
    """Build a chart-ready aggregation query for agent spans."""
    start, end = _resolve_time_bounds(req)
    tz = req.timezone or "UTC"

    source_filter = _spans_source_filter_sql(pb, req, start, end)
    group_refs = req.group_by or []
    resolved_groups = resolve_group_by(pb, group_refs) if group_refs else []

    metric_plans = [_metric_plan(metric, pb) for metric in req.metrics]
    metric_exprs = [expr for plan in metric_plans for expr in plan.expressions]
    metric_outputs = [output for plan in metric_plans for output in plan.outputs]
    bucket_by = req.bucket_by
    numeric_bucket = (
        bucket_by if isinstance(bucket_by, AgentSpanStatsNumericBucketSpec) else None
    )
    default_group_by = (
        numeric_bucket.group_by
        if numeric_bucket is not None and numeric_bucket.group_by
        else _conversation_group_by()
    )
    group_filters = span_group_filters(
        req.group_filters,
        default_group_by=default_group_by,
    )
    if numeric_bucket is not None and not metric_outputs:
        metric_outputs = [_count_metric_output()]
    columns, column_metadata = (
        _numeric_bucket_response_columns(metric_outputs)
        if numeric_bucket is not None
        else _response_columns(group_refs, metric_outputs)
    )

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

    if numeric_bucket is not None:
        raw_sql = _build_numeric_bucket_stats_query(
            source_filter=source_filter,
            bucket=numeric_bucket,
            metric_exprs=metric_exprs,
            agg_selects=agg_selects,
            outer_metric_selects=outer_metric_selects,
            group_filters=group_filters,
            pb=pb,
        )
        return AgentSpanStatsQueryBuildResult(
            sql=safely_format_sql(raw_sql, logger),
            columns=columns,
            column_metadata=column_metadata,
            parameters=pb.get_params(),
            granularity_seconds=None,
            start=start,
            end=end,
            bucket_type="number",
        )

    granularity_seconds = _resolve_granularity(req, start, end)
    # Whole unix seconds: a fractional float trips ClickHouse Int64 param parsing.
    start_epoch = int(start.replace(tzinfo=datetime.timezone.utc).timestamp())
    end_epoch = int(end.replace(tzinfo=datetime.timezone.utc).timestamp())
    start_param = pb.add_param(start_epoch)
    end_param = pb.add_param(end_epoch)
    tz_param = pb.add_param(tz)
    bucket_interval_param = pb.add_param(granularity_seconds)
    group_limit_slot = None
    if resolved_groups:
        group_limit = _effective_group_limit(req, start, end, granularity_seconds)
        group_limit_slot = pb.add(group_limit, param_type="UInt64")

    raw_sql = _build_stats_query(
        source_filter=source_filter,
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
        group_filters=group_filters,
        pb=pb,
    )

    return AgentSpanStatsQueryBuildResult(
        sql=safely_format_sql(raw_sql, logger),
        columns=columns,
        column_metadata=column_metadata,
        parameters=pb.get_params(),
        granularity_seconds=granularity_seconds,
        start=start,
        end=end,
        bucket_type="time",
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


def _spans_source_filter_sql(
    pb: ParamBuilder,
    req: AgentSpanStatsReq,
    start: datetime.datetime,
    end: datetime.datetime,
) -> _SpanSourceFilterSQL:
    pid_slot = pb.add(req.project_id, param_type="String")
    where_conditions = [_project_filter_sql(_span_col(_COL_PROJECT_ID), pid_slot)]
    add_time_filters(
        where_conditions,
        pb,
        started_after=start,
        started_before=end,
    )
    if req.query is not None:
        where_conditions.append(compile_agent_query(req.query, pb))
    # The base relation carries cost columns only when the request needs them;
    # attribution then wraps that base so identity columns inherit from their
    # trace while any cost columns pass through untouched.
    base = (
        cost_augmented_source_sql(pb, req.project_id)
        if _stats_requires_costs(req)
        else _SPANS_TABLE
    )
    source = base
    if _stats_references_identity(req):
        source = agent_trace_attribution.attributed_spans_source(
            pb,
            project_id=req.project_id,
            started_after=start,
            started_before=end,
            base_relation=base,
        )
    return _SpanSourceFilterSQL(where=" AND ".join(where_conditions), source=source)


def _stats_references_identity(req: AgentSpanStatsReq) -> bool:
    """Whether a stats request touches a trace-attributed identity column.

    Checks the filter, every group-by (top-level, numeric-bucket, and
    group-filter), and metric value refs, so any identity reference pulls in the
    attributed source. Errs toward attributing — a missed reference would read
    raw values while the filter expects attributed ones.
    """
    if agent_trace_attribution.query_references_identity(req.query):
        return True
    group_refs = list(req.group_by)
    bucket = req.bucket_by
    if isinstance(bucket, AgentSpanStatsNumericBucketSpec):
        group_refs += list(bucket.group_by)
    for group_filter in req.group_filters or []:
        group_refs += list(group_filter.group_by or [])
    field_keys = [
        ref.key for ref in group_refs if ref.source in _FIELD_GROUP_BY_SOURCES
    ]
    for metric in req.metrics:
        value = metric.value
        if value is not None and value.source in _FIELD_GROUP_BY_SOURCES:
            field_keys.append(value.key)
    return agent_trace_attribution.fields_reference_identity(field_keys)


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
        alias = group_by_ref_alias(group_ref)
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
                value_type=output.value_type,
                metric=output.metric_alias,
                aggregation=output.aggregation_label,
            )
        )

    return columns, metadata


def _numeric_bucket_response_columns(
    metric_outputs: list[_MetricOutput],
) -> tuple[list[str], list[AgentSpanStatsColumn]]:
    """Build response columns for numeric value-bucketed stats."""
    columns = [
        _RESPONSE_BUCKET_INDEX_COLUMN,
        _RESPONSE_BUCKET_MIN_COLUMN,
        _RESPONSE_BUCKET_MAX_COLUMN,
    ]
    metadata = [
        AgentSpanStatsColumn(
            name=_RESPONSE_BUCKET_INDEX_COLUMN,
            role="bucket",
            value_type=_VALUE_TYPE_NUMBER,
        ),
        AgentSpanStatsColumn(
            name=_RESPONSE_BUCKET_MIN_COLUMN,
            role="bucket",
            value_type=_VALUE_TYPE_NUMBER,
        ),
        AgentSpanStatsColumn(
            name=_RESPONSE_BUCKET_MAX_COLUMN,
            role="bucket",
            value_type=_VALUE_TYPE_NUMBER,
        ),
    ]

    for output in metric_outputs:
        columns.append(output.name)
        metadata.append(
            AgentSpanStatsColumn(
                name=output.name,
                role="metric",
                value_type=output.value_type,
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
        outputs=_metric_outputs(metric, metric_col, valid_col, metric_sql.value_type),
    )


def _metric_sql(metric: AgentSpanStatsMetricSpec, pb: ParamBuilder) -> _MetricSQL:
    """Return the per-span value expression and validity guard for a metric."""
    resolved = span_value_sql(metric.value, pb, expected_type=metric.value_type)
    return _MetricSQL(
        value_sql=resolved.value_sql,
        valid_sql=resolved.valid_sql,
        value_type=resolved.value_type,
    )


def _numeric_bucket_sql(
    bucket: AgentSpanStatsNumericBucketSpec,
    pb: ParamBuilder,
) -> _MetricSQL:
    """Resolve the numeric value expression used for value-range bucketing."""
    if bucket.value is None:
        raise ValueError("numeric bucket must set value")
    resolved = span_value_sql(bucket.value, pb, expected_type=_VALUE_TYPE_NUMBER)
    return _MetricSQL(
        value_sql=resolved.value_sql,
        valid_sql=resolved.valid_sql,
        value_type=resolved.value_type,
    )


def _metric_outputs(
    metric: AgentSpanStatsMetricSpec,
    metric_col: str,
    valid_col: str,
    metric_value_type: AgentSpanStatsColumnValueType,
) -> list[_MetricOutput]:
    """Build all aggregate output columns requested for one metric."""
    outputs: list[_MetricOutput] = []

    for agg in metric.aggregations:
        outputs.append(
            _aggregation_output(
                metric.alias,
                agg,
                metric_col,
                valid_col,
                metric_value_type,
            )
        )

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
                value_type=_VALUE_TYPE_NUMBER,
            )
        )

    return outputs


def _count_metric_output() -> _MetricOutput:
    return _MetricOutput(
        name="count",
        metric_alias="rows",
        aggregation_label="count",
        aggregate_sql="count()",
        outer_sql=f"COALESCE({_CTE_AGGREGATED_DATA}.count, 0)",
        value_type=_VALUE_TYPE_NUMBER,
    )


def _aggregation_output(
    metric_alias: str,
    agg: AgentSpanStatsAggregation,
    metric_col: str,
    valid_col: str,
    metric_value_type: AgentSpanStatsColumnValueType,
) -> _MetricOutput:
    name = _output_name(agg, metric_alias)
    coalesce_empty = agg in _ZERO_FILL_AGGREGATIONS

    if agg == _AGG_SUM:
        aggregate_sql = f"sumOrNull(if({valid_col}, {metric_col}, NULL))"
        value_type = _VALUE_TYPE_NUMBER
    elif agg == _AGG_AVG:
        aggregate_sql = f"avgOrNull(if({valid_col}, {metric_col}, NULL))"
        value_type = _VALUE_TYPE_NUMBER
    elif agg == _AGG_MIN:
        aggregate_sql = f"minOrNull(if({valid_col}, {metric_col}, NULL))"
        value_type = metric_value_type
    elif agg == _AGG_MAX:
        aggregate_sql = f"maxOrNull(if({valid_col}, {metric_col}, NULL))"
        value_type = metric_value_type
    elif agg == _AGG_COUNT:
        aggregate_sql = f"countIf({valid_col})"
        value_type = _VALUE_TYPE_NUMBER
    elif agg == _AGG_COUNT_DISTINCT:
        # uniq (approx, memory-bounded); uniqExact OOMs on large projects.
        aggregate_sql = f"uniqIf({metric_col}, {valid_col})"
        value_type = _VALUE_TYPE_NUMBER
    elif agg == _AGG_COUNT_TRUE:
        aggregate_sql = f"countIf({valid_col} AND {metric_col} = 1)"
        value_type = _VALUE_TYPE_NUMBER
    elif agg == _AGG_COUNT_FALSE:
        aggregate_sql = f"countIf({valid_col} AND {metric_col} = 0)"
        value_type = _VALUE_TYPE_NUMBER
    else:
        raise ValueError(f"unsupported aggregation: {agg!r}")

    return _metric_output(
        name=name,
        metric_alias=metric_alias,
        aggregation_label=agg,
        aggregate_sql=aggregate_sql,
        coalesce_empty=coalesce_empty,
        value_type=value_type,
    )


def _metric_output(
    *,
    name: str,
    metric_alias: str,
    aggregation_label: str,
    aggregate_sql: str,
    coalesce_empty: bool,
    value_type: AgentSpanStatsColumnValueType,
) -> _MetricOutput:
    raw_outer_sql = f"{_CTE_AGGREGATED_DATA}.{name}"
    outer_sql = f"COALESCE({raw_outer_sql}, 0)" if coalesce_empty else raw_outer_sql
    return _MetricOutput(
        name=name,
        metric_alias=metric_alias,
        aggregation_label=aggregation_label,
        aggregate_sql=aggregate_sql,
        outer_sql=outer_sql,
        value_type=value_type,
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
    column = resolve_agent_span_field_column(group_ref.key)
    return _COLUMN_VALUE_TYPES.get(column, _VALUE_TYPE_STRING)


def _build_stats_query(
    *,
    source_filter: _SpanSourceFilterSQL,
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
    group_filters: list[AgentSpanGroupFilter],
    pb: ParamBuilder,
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
        return _build_ungrouped_stats_query(
            source_filter=source_filter,
            parts=parts,
            group_filters=group_filters,
            pb=pb,
        )

    assert group_limit_slot is not None
    return _build_grouped_stats_query(
        source_filter=source_filter,
        resolved_groups=resolved_groups,
        group_limit_slot=group_limit_slot,
        parts=parts,
    )


def _build_numeric_bucket_stats_query(
    *,
    source_filter: _SpanSourceFilterSQL,
    bucket: AgentSpanStatsNumericBucketSpec,
    metric_exprs: list[str],
    agg_selects: list[str],
    outer_metric_selects: list[str],
    group_filters: list[AgentSpanGroupFilter],
    pb: ParamBuilder,
) -> str:
    """Render one row per numeric value range over the full filtered span set."""
    bins_param = pb.add_param(bucket.bins)
    bins_uint = param_slot(bins_param, "UInt64")
    bins_float = param_slot(bins_param, "Float64")
    min_bound_sql = (
        param_slot(pb.add_param(bucket.min), "Float64")
        if bucket.min is not None
        else "min(bucket_value)"
    )
    max_bound_sql = (
        param_slot(pb.add_param(bucket.max), "Float64")
        if bucket.max is not None
        else "max(bucket_value)"
    )
    # bounds computed once as a scalar tuple (min, max, count).
    # ClickHouse does NOT materialize table CTEs - each reference re-scans
    # value_rows (re-decoding the attrs map). Do NOT convert back to a CTE.
    # Not min()/max() OVER (): the unbounded frame buffers all matched rows
    # (un-spillable, OOM-risk near the 16 GiB cap at scale); the extra scan is cheaper.
    bounds_min = f"{_BOUNDS_TUPLE}.min_bound"
    bounds_max = f"{_BOUNDS_TUPLE}.max_bound"
    bounds_count = f"{_BOUNDS_TUPLE}.value_count"
    bucket_width_sql = (
        f"if({bounds_max} > {bounds_min}, "
        f"({bounds_max} - {bounds_min}) "
        f"/ {bins_float}, 1.0)"
    )
    bucket_index_raw_sql = (
        f"if({bounds_max} = {bounds_min}, "
        "toUInt64(0), "
        f"toUInt64(least(toFloat64({bins_uint}) - 1.0, floor("
        f"({_CTE_VALUE_ROWS}.bucket_value - {bounds_min}) "
        f"/ {bucket_width_sql}))))"
    )
    bucket_index_sql = bucket_index_raw_sql
    bucket_min_sql = (
        f"if({bounds_max} = {bounds_min}, "
        f"{bounds_min}, "
        f"{bounds_min} + "
        f"toFloat64({_CTE_ALL_BUCKETS}.{_BUCKET_COLUMN}) * {bucket_width_sql})"
    )
    bucket_max_sql = (
        f"if({bounds_max} = {bounds_min}, "
        f"{bounds_max}, "
        f"if({_CTE_ALL_BUCKETS}.{_BUCKET_COLUMN} = {bins_uint} - toUInt64(1), "
        f"{bounds_max}, "
        f"{bounds_min} + "
        f"toFloat64({_CTE_ALL_BUCKETS}.{_BUCKET_COLUMN} + 1) * "
        f"{bucket_width_sql}))"
    )
    metric_select_sql = ",\n          ".join(metric_exprs)
    metric_select_clause = (
        f",\n          {metric_select_sql}" if metric_select_sql else ""
    )
    agg_select_sql = ",\n          ".join(agg_selects)
    outer_metric_sql = ",\n      ".join(outer_metric_selects)
    if bucket.group_by and bucket.measure is not None:
        bucket_measure = span_measure_sql(bucket.measure, pb)
        if bucket_measure.value_type != _VALUE_TYPE_NUMBER:
            raise ValueError("numeric group bucket measure must produce a number")
        resolved_groups = resolve_group_by(pb, bucket.group_by)
        ensure_group_filters_match(
            group_filters, bucket.group_by, context="numeric bucket"
        )
        group_by_clause = ", ".join(expr for expr, _ in resolved_groups)
        having = group_filters_having_sql(pb, group_filters)
        having_sql = f"HAVING {having}" if having else ""
        value_rows_sql = f"""
        SELECT
          {bucket_measure.aggregate_sql} AS bucket_value
        FROM {_CTE_FILTERED_SPANS} {_SPAN_ALIAS}
        GROUP BY {group_by_clause}
        {having_sql}
        """
    else:
        bucket_metric = _numeric_bucket_sql(bucket, pb)
        value_rows_sql = f"""
        SELECT
          {bucket_metric.value_sql} AS bucket_value{metric_select_clause}
        FROM {_CTE_FILTERED_SPANS} {_SPAN_ALIAS}
        WHERE {bucket_metric.valid_sql}
          AND isNotNull({bucket_metric.value_sql})
          AND isFinite({bucket_metric.value_sql})
        """
    return f"""
    WITH
      {_CTE_FILTERED_SPANS} AS (
        SELECT *
        FROM {source_filter.source} {_SPAN_ALIAS}
        {source_filter.clause}
      ),
      {_CTE_VALUE_ROWS} AS (
        {value_rows_sql}
      ),
      (
        SELECT CAST(tuple(
          toFloat64({min_bound_sql}),
          toFloat64({max_bound_sql}),
          count()
        ) AS Tuple(min_bound Nullable(Float64), max_bound Nullable(Float64), value_count UInt64))
        FROM {_CTE_VALUE_ROWS}
      ) AS {_BOUNDS_TUPLE},
      {_CTE_ALL_BUCKETS} AS (
        SELECT toUInt64(number) AS {_BUCKET_COLUMN}
        FROM numbers({bins_uint})
      ),
      {_CTE_AGGREGATED_DATA} AS (
        SELECT
          {bucket_index_sql} AS {_BUCKET_COLUMN},
          {agg_select_sql}
        FROM {_CTE_VALUE_ROWS}
        WHERE {_CTE_VALUE_ROWS}.bucket_value >= {bounds_min}
          AND {_CTE_VALUE_ROWS}.bucket_value <= {bounds_max}
        GROUP BY {_BUCKET_COLUMN}
      )
    SELECT
      {_CTE_ALL_BUCKETS}.{_BUCKET_COLUMN} AS {_RESPONSE_BUCKET_INDEX_COLUMN},
      {bucket_min_sql} AS {_RESPONSE_BUCKET_MIN_COLUMN},
      {bucket_max_sql} AS {_RESPONSE_BUCKET_MAX_COLUMN},
      {outer_metric_sql}
    FROM {_CTE_ALL_BUCKETS}
    LEFT JOIN {_CTE_AGGREGATED_DATA}
      ON {_CTE_ALL_BUCKETS}.{_BUCKET_COLUMN} = {_CTE_AGGREGATED_DATA}.{_BUCKET_COLUMN}
    WHERE {bounds_count} > 0
      AND (
        {bounds_max} > {bounds_min}
        OR {_CTE_ALL_BUCKETS}.{_BUCKET_COLUMN} = 0
      )
    ORDER BY {_RESPONSE_BUCKET_INDEX_COLUMN}
    """


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
    source_filter: _SpanSourceFilterSQL,
    parts: _StatsQuerySQLParts,
    group_filters: list[AgentSpanGroupFilter],
    pb: ParamBuilder,
) -> str:
    """Render one row per time bucket for the full filtered span set."""
    group_filter_ctes, stats_source_cte = _group_filter_ctes(pb, group_filters)
    return f"""
    WITH
      {_CTE_ALL_BUCKETS} AS (
        {parts.all_buckets_sql}
      ),
      {_CTE_FILTERED_SPANS} AS (
        SELECT *
        FROM {source_filter.source} {_SPAN_ALIAS}
        {source_filter.clause}
      ){group_filter_ctes},
      {_CTE_AGGREGATED_DATA} AS (
        SELECT
          {_BUCKET_COLUMN},
          {parts.agg_select_sql}
        FROM (
          SELECT
            {parts.bucket_expr} AS {_BUCKET_COLUMN},
            {parts.metric_select_sql}
          FROM {stats_source_cte} {_SPAN_ALIAS}
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


def _group_filter_ctes(
    pb: ParamBuilder,
    group_filters: list[AgentSpanGroupFilter],
) -> tuple[str, str]:
    if not group_filters:
        return "", _CTE_FILTERED_SPANS

    ctes: list[str] = []
    source_cte = _CTE_FILTERED_SPANS
    for idx, filter_ in enumerate(group_filters):
        if not filter_.group_by:
            raise ValueError("group filters used in stats require group_by")
        resolved_groups = resolve_group_by(pb, filter_.group_by)
        select_group_cols = ", ".join(
            f"{expr} AS {alias}" for expr, alias in resolved_groups
        )
        group_by_clause = ", ".join(alias for _, alias in resolved_groups)
        having = group_filters_having_sql(pb, [filter_])
        qualified_cte = f"qualified_groups_{idx}"
        next_source_cte = (
            _CTE_FILTERED_METRIC_SPANS
            if idx == len(group_filters) - 1
            else f"filtered_metric_spans_{idx}"
        )
        join_sql = " AND ".join(
            f"{expr} = q.{alias}" for expr, alias in resolved_groups
        )
        ctes.append(
            f""",
      {qualified_cte} AS (
        SELECT {select_group_cols}
        FROM {source_cte} {_SPAN_ALIAS}
        GROUP BY {group_by_clause}
        HAVING {having}
      ),
      {next_source_cte} AS (
        SELECT {_SPAN_ALIAS}.*
        FROM {source_cte} {_SPAN_ALIAS}
        INNER JOIN {qualified_cte} q
          ON {join_sql}
      )"""
        )
        source_cte = next_source_cte

    return "".join(ctes), source_cte


def _build_grouped_stats_query(
    *,
    source_filter: _SpanSourceFilterSQL,
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
        FROM {source_filter.source} {_SPAN_ALIAS}
        {source_filter.clause}
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
