"""Query builder for the GenAI agent observability system.

Every SELECT emitted against the spans / agents / agent_versions / messages
tables is constructed here via `make_*_query` functions. Consumers build a
`ParamBuilder`, call the appropriate `make_*_query(pb, req)`, then run the
returned SQL through the server's `_query` method.

Keeping the SQL in this module makes it unit-testable without a live ClickHouse:
see `tests/trace_server/query_builder/test_agent_query_builder.py`.
"""

from __future__ import annotations

import datetime
import re
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import Any, NamedTuple, TypeAlias

from weave.trace_server.agents import semconv
from weave.trace_server.agents.constants import (
    OP_INVOKE_AGENT,
    SEARCH_CONTENT_PREVIEW_CHARS,
    SPAN_GROUP_AGGREGATE_COLS,
    SPAN_GROUP_RESULT_COLS,
)
from weave.trace_server.agents.span_costs import (
    COST_COLUMN_NAMES,
    COST_DERIVED_METRIC_NAMES,
    GROUPED_COST_ALIASES,
    cost_augmented_source_sql,
)
from weave.trace_server.agents.types import (
    AGENT_CUSTOM_ATTR_SOURCE_VALUE_TYPES,
    AgentConversationChatReq,
    AgentCustomAttrsSchemaReq,
    AgentGroupByRef,
    AgentSearchReq,
    AgentSortBy,
    AgentSpanGroupDistributionSpec,
    AgentSpanGroupFilter,
    AgentSpanMeasureSpec,
    AgentSpanSchema,
    AgentSpansQueryReq,
    AgentSpanStatsAggregation,
    AgentSpanStatsColumnValueType,
    AgentSpanStatsDerivedMetric,
    AgentSpanStatsValueType,
    AgentSpanValueRef,
    AgentsQueryReq,
    AgentVersionsQueryReq,
    group_by_ref_alias,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder import agent_trace_attribution
from weave.trace_server.query_builder.agent_custom_attrs import (
    custom_attr_value_or_null,
)

# ---------------------------------------------------------------------------
# Column whitelists — only these can appear in WHERE/ORDER BY/GROUP BY
# ---------------------------------------------------------------------------

# Columns on spans that can be filtered with equality/IN.
SPAN_FILTERABLE_COLS: frozenset[str] = frozenset(
    {
        "operation_name",
        "provider_name",
        "agent_name",
        "agent_version",
        "request_model",
        "response_model",
        "tool_name",
        "tool_type",
        "conversation_id",
        "status_code",
        "error_type",
        "span_kind",
        "trace_id",
        "span_id",
        "wb_run_id",
    }
)

SPAN_GROUP_BY_COLS: frozenset[str] = SPAN_FILTERABLE_COLS.union(
    frozenset(
        {
            "agent_id",
            "tool_call_id",
            "wb_user_id",
        }
    )
)

SPAN_SORTABLE_COLS: frozenset[str] = SPAN_FILTERABLE_COLS.union(
    frozenset(
        {
            "span_name",
            "started_at",
            "ended_at",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
            "output_type",
            "request_temperature",
            "request_max_tokens",
            "request_top_p",
            "wb_run_step",
            "server_address",
        }
    )
)

AGENT_SORTABLE_COLS: frozenset[str] = frozenset(
    {
        "last_seen",
        "first_seen",
        "invocation_count",
        "span_count",
        "total_input_tokens",
        "error_count",
    }
)

# Valid SQL identifier (used to validate group_by aliases).
_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Sources that read from a Map(...) column on spans, keyed by user-supplied key.
_CUSTOM_ATTR_SOURCES: frozenset[str] = frozenset(AGENT_CUSTOM_ATTR_SOURCE_VALUE_TYPES)
_FIELD_GROUP_BY_SOURCES: frozenset[str] = frozenset({"field", "column"})

_VALUE_TYPE_STRING: AgentSpanStatsValueType = "string"
_VALUE_TYPE_NUMBER: AgentSpanStatsValueType = "number"
_VALUE_TYPE_BOOLEAN: AgentSpanStatsValueType = "boolean"
_VALUE_TYPE_DATETIME: AgentSpanStatsColumnValueType = "datetime"

_SOURCE_DERIVED = "derived"
_SOURCE_FIELD = "field"
_SOURCE_CUSTOM_ATTRS_STRING = "custom_attrs_string"
_SOURCE_CUSTOM_ATTRS_INT = "custom_attrs_int"
_SOURCE_CUSTOM_ATTRS_FLOAT = "custom_attrs_float"
_SOURCE_CUSTOM_ATTRS_BOOL = "custom_attrs_bool"
_NUMERIC_DISTRIBUTION_SOURCES = {
    _SOURCE_CUSTOM_ATTRS_INT,
    _SOURCE_CUSTOM_ATTRS_FLOAT,
}
_CATEGORICAL_DISTRIBUTION_SOURCES = {
    _SOURCE_CUSTOM_ATTRS_STRING,
    _SOURCE_CUSTOM_ATTRS_BOOL,
}

_AGG_SUM: AgentSpanStatsAggregation = "sum"
_AGG_AVG: AgentSpanStatsAggregation = "avg"
_AGG_MIN: AgentSpanStatsAggregation = "min"
_AGG_MAX: AgentSpanStatsAggregation = "max"
_AGG_COUNT: AgentSpanStatsAggregation = "count"
_AGG_COUNT_DISTINCT: AgentSpanStatsAggregation = "count_distinct"
_AGG_COUNT_TRUE: AgentSpanStatsAggregation = "count_true"
_AGG_COUNT_FALSE: AgentSpanStatsAggregation = "count_false"

_ALLOWED_MEASURE_AGGS_BY_TYPE: dict[
    AgentSpanStatsColumnValueType, frozenset[AgentSpanStatsAggregation]
] = {
    _VALUE_TYPE_DATETIME: frozenset(
        {_AGG_MIN, _AGG_MAX, _AGG_COUNT, _AGG_COUNT_DISTINCT}
    ),
    _VALUE_TYPE_NUMBER: frozenset(
        {_AGG_SUM, _AGG_AVG, _AGG_MIN, _AGG_MAX, _AGG_COUNT, _AGG_COUNT_DISTINCT}
    ),
    _VALUE_TYPE_BOOLEAN: frozenset(
        {_AGG_COUNT, _AGG_COUNT_DISTINCT, _AGG_COUNT_TRUE, _AGG_COUNT_FALSE}
    ),
    _VALUE_TYPE_STRING: frozenset({_AGG_COUNT, _AGG_COUNT_DISTINCT}),
}

_DERIVED_DURATION_MS: AgentSpanStatsDerivedMetric = "duration_ms"
_DERIVED_TOTAL_TOKENS: AgentSpanStatsDerivedMetric = "total_tokens"
_DERIVED_IS_ERROR: AgentSpanStatsDerivedMetric = "is_error"
_DERIVED_IS_INVOCATION: AgentSpanStatsDerivedMetric = "is_invocation"
_STATUS_CODE_ERROR = "ERROR"

_CUSTOM_ATTR_VALUE_TYPES: dict[str, AgentSpanStatsValueType] = {
    _SOURCE_CUSTOM_ATTRS_STRING: _VALUE_TYPE_STRING,
    _SOURCE_CUSTOM_ATTRS_INT: _VALUE_TYPE_NUMBER,
    _SOURCE_CUSTOM_ATTRS_FLOAT: _VALUE_TYPE_NUMBER,
    _SOURCE_CUSTOM_ATTRS_BOOL: _VALUE_TYPE_BOOLEAN,
}

_CUSTOM_ATTR_SCHEMA_SOURCES: tuple[tuple[str, str], ...] = tuple(
    AGENT_CUSTOM_ATTR_SOURCE_VALUE_TYPES.items()
)

SpanGroupKeyValue: TypeAlias = str | int | float | bool | None


class SpanGroupDistributionContext(NamedTuple):
    group_key_sql: str
    group_values_slot: str


_CORE_SPAN_VALUE_TYPES: dict[str, AgentSpanStatsColumnValueType] = {
    "trace_id": _VALUE_TYPE_STRING,
    "span_id": _VALUE_TYPE_STRING,
    "parent_span_id": _VALUE_TYPE_STRING,
    "span_name": _VALUE_TYPE_STRING,
    "span_kind": _VALUE_TYPE_STRING,
    "started_at": _VALUE_TYPE_DATETIME,
    "ended_at": _VALUE_TYPE_DATETIME,
    "status_code": _VALUE_TYPE_STRING,
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

SPAN_VALUE_TYPES: dict[str, AgentSpanStatsColumnValueType] = {
    **{
        column: _SEMCONV_TYPE_TO_STATS_TYPE[semconv.ATTRIBUTES[key].type]
        for key, column in semconv.CANONICAL_KEY_TO_COLUMN.items()
    },
    **_CORE_SPAN_VALUE_TYPES,
}


@dataclass(frozen=True, slots=True)
class SpanValueSQL:
    value_sql: str
    valid_sql: str
    value_type: AgentSpanStatsColumnValueType


@dataclass(frozen=True, slots=True)
class SpanMeasureSQL:
    alias: str
    aggregate_sql: str
    value_type: AgentSpanStatsColumnValueType


@dataclass(frozen=True, slots=True)
class _FilterSQL:
    where: str


# ---------------------------------------------------------------------------
# Column projections
# ---------------------------------------------------------------------------


def _projection(cols: list[str], *, table_alias: str | None = None) -> str:
    unknown = [c for c in cols if c not in AgentSpanSchema.model_fields]
    if unknown:
        raise ValueError(
            f"projection contains fields not in AgentSpanSchema: {unknown}"
        )
    if table_alias:
        return ", ".join(f"{table_alias}.{c} AS {c}" for c in cols)
    return ", ".join(cols)


# Spans list query: scalar/short projection used for the spans table.
# Custom-attr Maps and large blobs (messages, payloads, raw_span_dump) are
# pulled in by `_SPANS_DETAILS_FIELD_NAMES` only when the caller opts in via
# `include_details`.
_SPANS_LIST_FIELD_NAMES = [
    "project_id",
    "trace_id",
    "span_id",
    "parent_span_id",
    "span_name",
    "span_kind",
    "started_at",
    "ended_at",
    "status_code",
    "status_message",
    "operation_name",
    "provider_name",
    "agent_name",
    "agent_id",
    "agent_description",
    "agent_version",
    "request_model",
    "response_model",
    "response_id",
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "conversation_id",
    "conversation_name",
    "tool_name",
    "tool_type",
    "tool_call_id",
    "finish_reasons",
    "error_type",
    "request_temperature",
    "request_max_tokens",
    "request_top_p",
    "request_frequency_penalty",
    "request_presence_penalty",
    "request_seed",
    "request_stop_sequences",
    "request_choice_count",
    "output_type",
    "compaction_items_before",
    "compaction_items_after",
    "server_address",
    "server_port",
    "wb_user_id",
    "wb_run_id",
    "wb_run_step",
    "wb_run_step_end",
]
SPANS_LIST_COLS: str = _projection(_SPANS_LIST_FIELD_NAMES)

# Per-span cost columns, projected only when the caller sets `include_costs`.
# These are computed by the cost-augmented spans source, not stored columns.
SPANS_COST_COLS: str = _projection(list(COST_COLUMN_NAMES))
QUALIFIED_SPANS_COST_COLS: str = _projection(list(COST_COLUMN_NAMES), table_alias="s")
_SPAN_COST_SORTABLE_COLS: frozenset[str] = frozenset(COST_COLUMN_NAMES)

# Detail-only fields: heavy text/array payloads. Included only when the
# caller sets `include_details` (the span detail panel does this; the main
# spans table does not).
#
# The `*_refs` columns are stored in internal-ref form by `extract_genai_span`
# so the response-side int→ext converter can round-trip them. Pre-fix rows
# may still hold external `weave:///` refs; those will trip the strict
# converter at read time and need a backfill.
_SPANS_DETAILS_FIELD_NAMES = [
    "reasoning_content",
    "tool_description",
    "tool_definitions",
    "input_messages",
    "output_messages",
    "system_instructions",
    "tool_call_arguments",
    "tool_call_result",
    "compaction_summary",
    "content_refs",
    "artifact_refs",
    "object_refs",
    "raw_span_dump",
]
SPANS_DETAILS_COLS: str = _projection(_SPANS_DETAILS_FIELD_NAMES)


def _custom_attr_field_name(ref: AgentSpanValueRef) -> str:
    return f"{ref.source}.{ref.key}"


def _custom_attr_map_projection(
    pb: ParamBuilder,
    refs: list[AgentSpanValueRef],
    *,
    table_alias: str = "s",
) -> str:
    """Project only selected custom-attribute Map keys for spans table rows."""
    keys_by_source: dict[str, set[str]] = {
        source: set() for source in sorted(_CUSTOM_ATTR_SOURCES)
    }
    for ref in refs:
        if ref.source in keys_by_source:
            keys_by_source[ref.source].add(str(ref.key))

    projections: list[str] = []
    for source, keys in keys_by_source.items():
        if not keys:
            continue
        keys_slot = pb.add(sorted(keys), param_type="Array(String)")
        projections.append(
            f"mapFilter((k, v) -> has({keys_slot}, k), "
            f"{table_alias}.{source}) AS {source}"
        )
    return ", " + ", ".join(projections) if projections else ""


def _custom_attr_sort_exprs(
    pb: ParamBuilder,
    refs: list[AgentSpanValueRef],
    *,
    table_alias: str = "s",
) -> dict[str, str]:
    exprs: dict[str, str] = {}
    for ref in refs:
        if ref.source not in _CUSTOM_ATTR_VALUE_TYPES:
            continue
        value_sql = span_value_sql(
            ref,
            pb,
            table_alias=table_alias,
        )
        exprs[_custom_attr_field_name(ref)] = (
            f"if({value_sql.valid_sql}, {value_sql.value_sql}, NULL)"
        )
    return exprs


# Chat view projection: includes messages and tool data but skips raw dumps,
# custom attrs, W&B integration IDs, and request params not needed for rendering.
_CHAT_VIEW_FIELD_NAMES = [
    "project_id",
    "trace_id",
    "span_id",
    "parent_span_id",
    "span_name",
    "span_kind",
    "started_at",
    "ended_at",
    "status_code",
    "status_message",
    "operation_name",
    "provider_name",
    "agent_name",
    "agent_id",
    "agent_description",
    "agent_version",
    "request_model",
    "response_model",
    "response_id",
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "reasoning_content",
    "conversation_id",
    "conversation_name",
    "tool_name",
    "tool_type",
    "tool_call_id",
    "tool_description",
    "tool_definitions",
    "finish_reasons",
    "input_messages",
    "output_messages",
    "system_instructions",
    "tool_call_arguments",
    "tool_call_result",
    "compaction_summary",
    "compaction_items_before",
    "compaction_items_after",
    "content_refs",
    "artifact_refs",
    "object_refs",
]
CHAT_VIEW_COLS: str = _projection(_CHAT_VIEW_FIELD_NAMES)
QUALIFIED_CHAT_VIEW_COLS: str = _projection(_CHAT_VIEW_FIELD_NAMES, table_alias="s")

# ---------------------------------------------------------------------------
# Clause helpers (mutate pb in-place, append to conditions)
# ---------------------------------------------------------------------------


def build_order_by(
    sort_by: list[AgentSortBy] | None,
    allowed: frozenset[str],
    default: str,
    column_exprs: dict[str, str] | None = None,
) -> str:
    """Build a safe ORDER BY clause, rejecting unknown columns.

    If column_exprs is provided, the column name is mapped to the given SQL
    expression (e.g. {"provider_name": "arrayElement(provider_names, 1)"}).
    """
    if not sort_by:
        return default
    parts: list[str] = []
    for s in sort_by:
        if s.field not in allowed:
            raise ValueError(f"Invalid sort field: {s.field!r}")
        if s.direction not in {"asc", "desc"}:
            raise ValueError(f"Invalid sort direction: {s.direction!r}")
        expr = column_exprs.get(s.field, s.field) if column_exprs else s.field
        parts.append(f"{expr} {s.direction}")
    return ", ".join(parts)


def add_time_filters(
    conditions: list[str],
    pb: ParamBuilder,
    *,
    started_after: datetime.datetime | None,
    started_before: datetime.datetime | None,
    column: str = "s.started_at",
) -> None:
    """Add started_at time range conditions."""
    if started_after:
        after_slot = pb.add(started_after, param_type="DateTime64(6)")
        conditions.append(f"{column} >= {after_slot}")
    if started_before:
        before_slot = pb.add(started_before, param_type="DateTime64(6)")
        conditions.append(f"{column} < {before_slot}")


def _pagination_slots(pb: ParamBuilder, limit: int, offset: int) -> tuple[str, str]:
    """Add limit/offset params and return (limit_slot, offset_slot).

    Bounds (`0 <= limit <= MAX_AGENT_QUERY_LIMIT`, `offset >= 0`) are
    enforced by Pydantic on the request models; this function trusts those
    invariants rather than re-clamping.
    """
    limit_slot = pb.add(limit, param_type="UInt64")
    offset_slot = pb.add(offset, param_type="UInt64")
    return limit_slot, offset_slot


# ---------------------------------------------------------------------------
# Group-by resolution
# ---------------------------------------------------------------------------


def resolve_group_by(
    pb: ParamBuilder,
    refs: list[AgentGroupByRef],
    *,
    table_alias: str = "s",
) -> list[tuple[str, str]]:
    """Resolve group_by refs to [(sql_expr, alias), ...].

    Validates that:
      - column refs target an allowlisted span column (`SPAN_GROUP_BY_COLS`)
      - custom attribute refs target one of the typed Map columns
      - the resulting alias is a valid SQL identifier
      - aliases are unique within the request
    """
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for ref in refs:
        alias = group_by_ref_alias(ref)
        if not _IDENT_RE.match(alias):
            raise ValueError(
                f"group_by alias must match [a-zA-Z_][a-zA-Z0-9_]*, got {alias!r}"
            )
        if alias in seen:
            raise ValueError(f"duplicate group_by alias: {alias!r}")
        seen.add(alias)

        if ref.source in _FIELD_GROUP_BY_SOURCES:
            column = resolve_agent_span_field_column(ref.key)
            if column not in SPAN_GROUP_BY_COLS:
                raise ValueError(f"group_by field {ref.key!r} is not in the allowlist")
            sql_expr = f"{table_alias}.{column}"
        elif ref.source in _CUSTOM_ATTR_SOURCES:
            key_slot = pb.add(str(ref.key), param_type="String")
            sql_expr = custom_attr_value_or_null(table_alias, ref.source, key_slot)
        else:
            raise ValueError(f"unknown group_by source: {ref.source!r}")
        out.append((sql_expr, alias))
    return out


def resolve_agent_span_field_column(field: str) -> str:
    """Resolve a public span field name to its storage column when known."""
    return semconv.FILTERABLE_KEY_TO_COLUMN.get(field, field)


# ---------------------------------------------------------------------------
# Span value and grouped measure resolution
# ---------------------------------------------------------------------------


def span_value_sql(
    value: AgentSpanValueRef,
    pb: ParamBuilder,
    *,
    table_alias: str = "s",
    expected_type: AgentSpanStatsValueType
    | AgentSpanStatsColumnValueType
    | None = None,
) -> SpanValueSQL:
    """Resolve a value ref to a span-level SQL expression and validity guard."""
    if value.source == _SOURCE_DERIVED:
        out = _derived_value_sql(value.key, pb, table_alias=table_alias)
    elif value.source == _SOURCE_FIELD:
        col = resolve_agent_span_field_column(value.key)
        value_type = SPAN_VALUE_TYPES.get(col)
        if value_type is None:
            raise ValueError(f"field {value.key!r} is not aggregatable")
        value_sql = f"{table_alias}.{col}"
        if value_type == _VALUE_TYPE_NUMBER:
            value_sql = f"toFloat64({value_sql})"
        out = SpanValueSQL(value_sql=value_sql, valid_sql="1", value_type=value_type)
    elif value.source in _CUSTOM_ATTR_VALUE_TYPES:
        value_type = _CUSTOM_ATTR_VALUE_TYPES[value.source]
        key_slot = pb.add(str(value.key), param_type="String")
        source_column = f"{table_alias}.{value.source}"
        value_sql = f"{source_column}[{key_slot}]"
        if value_type == _VALUE_TYPE_NUMBER:
            value_sql = f"toFloat64({value_sql})"
        out = SpanValueSQL(
            value_sql=value_sql,
            valid_sql=f"mapContains({source_column}, {key_slot})",
            value_type=value_type,
        )
    else:
        raise ValueError(f"unknown value source: {value.source!r}")

    if expected_type is not None and out.value_type != expected_type:
        raise ValueError(
            f"value {value.key!r} has value_type {out.value_type!r}, "
            f"got {expected_type!r}"
        )
    return out


def _derived_value_sql(
    metric: str,
    pb: ParamBuilder,
    *,
    table_alias: str,
) -> SpanValueSQL:
    if metric == _DERIVED_DURATION_MS:
        started_at = f"{table_alias}.started_at"
        ended_at = f"{table_alias}.ended_at"
        duration = (
            f"toFloat64(toUnixTimestamp64Milli({ended_at}) - "
            f"toUnixTimestamp64Milli({started_at}))"
        )
        return SpanValueSQL(
            value_sql=f"if({ended_at} > {started_at}, {duration}, NULL)",
            valid_sql=f"{ended_at} > {started_at}",
            value_type=_VALUE_TYPE_NUMBER,
        )
    if metric == _DERIVED_TOTAL_TOKENS:
        return SpanValueSQL(
            value_sql=(
                f"toFloat64({table_alias}.input_tokens + "
                f"{table_alias}.output_tokens + {table_alias}.reasoning_tokens)"
            ),
            valid_sql="1",
            value_type=_VALUE_TYPE_NUMBER,
        )
    if metric == _DERIVED_IS_ERROR:
        return SpanValueSQL(
            value_sql=f"{table_alias}.status_code = '{_STATUS_CODE_ERROR}'",
            valid_sql="1",
            value_type=_VALUE_TYPE_BOOLEAN,
        )
    if metric == _DERIVED_IS_INVOCATION:
        op_slot = pb.add(OP_INVOKE_AGENT, param_type="String")
        return SpanValueSQL(
            value_sql=f"{table_alias}.operation_name = {op_slot}",
            valid_sql="1",
            value_type=_VALUE_TYPE_BOOLEAN,
        )
    if metric in COST_DERIVED_METRIC_NAMES:
        # The cost column (same name as the metric) is supplied by the
        # cost-augmented span source. NULL means the span's model had no
        # matching price, so guard it out of aggregates rather than scoring 0.
        return SpanValueSQL(
            value_sql=f"toFloat64({table_alias}.{metric})",
            valid_sql=f"isNotNull({table_alias}.{metric})",
            value_type=_VALUE_TYPE_NUMBER,
        )
    raise ValueError(f"unknown derived metric: {metric!r}")


def span_measure_sql(
    measure: AgentSpanMeasureSpec,
    pb: ParamBuilder,
    *,
    table_alias: str = "s",
) -> SpanMeasureSQL:
    """Resolve a grouped measure spec to a ClickHouse aggregate expression."""
    value_sql: SpanValueSQL | None = None
    if measure.value is not None:
        value_sql = span_value_sql(
            measure.value,
            pb,
            table_alias=table_alias,
            expected_type=measure.value_type,
        )

    valid_parts: list[str] = []
    if value_sql is not None:
        valid_parts.append(value_sql.valid_sql)
    if measure.filter is not None:
        from weave.trace_server.query_builder.agent_query_compiler import (
            compile_agent_query,
        )

        valid_parts.append(
            compile_agent_query(measure.filter, pb, table_alias=table_alias)
        )
    valid_sql = " AND ".join(f"({part})" for part in valid_parts) or "1"
    agg = measure.aggregation
    if value_sql is not None:
        allowed_aggs = _ALLOWED_MEASURE_AGGS_BY_TYPE[value_sql.value_type]
        if agg not in allowed_aggs:
            raise ValueError(
                f"aggregation {agg!r} is not valid for value_type "
                f"{value_sql.value_type!r}"
            )

    if agg == _AGG_COUNT:
        aggregate_sql = "count()" if valid_sql == "1" else f"countIf({valid_sql})"
        value_type = _VALUE_TYPE_NUMBER
    else:
        if value_sql is None:
            raise ValueError(f"aggregation {agg!r} requires a value")
        metric_sql = value_sql.value_sql
        if agg == _AGG_SUM:
            aggregate_sql = f"sumOrNull(if({valid_sql}, {metric_sql}, NULL))"
            value_type = _VALUE_TYPE_NUMBER
        elif agg == _AGG_AVG:
            aggregate_sql = f"avgOrNull(if({valid_sql}, {metric_sql}, NULL))"
            value_type = _VALUE_TYPE_NUMBER
        elif agg == _AGG_MIN:
            aggregate_sql = f"minOrNull(if({valid_sql}, {metric_sql}, NULL))"
            value_type = value_sql.value_type
        elif agg == _AGG_MAX:
            aggregate_sql = f"maxOrNull(if({valid_sql}, {metric_sql}, NULL))"
            value_type = value_sql.value_type
        elif agg == _AGG_COUNT_DISTINCT:
            # uniq (approx, memory-bounded); uniqExact OOMs on large projects.
            aggregate_sql = f"uniqIf({metric_sql}, {valid_sql})"
            value_type = _VALUE_TYPE_NUMBER
        elif agg == _AGG_COUNT_TRUE:
            if value_sql.value_type != _VALUE_TYPE_BOOLEAN:
                raise ValueError("count_true requires a boolean value")
            aggregate_sql = f"countIf({valid_sql} AND {metric_sql} = 1)"
            value_type = _VALUE_TYPE_NUMBER
        elif agg == _AGG_COUNT_FALSE:
            if value_sql.value_type != _VALUE_TYPE_BOOLEAN:
                raise ValueError("count_false requires a boolean value")
            aggregate_sql = f"countIf({valid_sql} AND {metric_sql} = 0)"
            value_type = _VALUE_TYPE_NUMBER
        else:
            raise ValueError(f"unsupported aggregation: {agg!r}")

    return SpanMeasureSQL(
        alias=measure.alias,
        aggregate_sql=aggregate_sql,
        value_type=value_type,
    )


def span_group_filters(
    filters: list[AgentSpanGroupFilter],
    *,
    default_group_by: list[AgentGroupByRef],
) -> list[AgentSpanGroupFilter]:
    """Fill omitted group_by refs on grouped aggregate filters."""
    return [
        filter_.model_copy(update={"group_by": filter_.group_by or default_group_by})
        for filter_ in filters
    ]


def ensure_group_filters_match(
    filters: list[AgentSpanGroupFilter],
    group_by: list[AgentGroupByRef],
    *,
    context: str,
) -> None:
    """Require HAVING-based group filters to target the active grouping."""
    for filter_ in filters:
        if filter_.group_by != group_by:
            raise ValueError(
                f"{context} group_filters must use the same group_by as the query"
            )


def _ensure_group_measure_aliases_do_not_collide(
    group_aliases: list[str], measures: list[AgentSpanMeasureSpec]
) -> None:
    """Reject dynamic measure aliases that would overwrite grouped row fields."""
    # TODO: surface this as a 4xx instead of a 500. The same check runs in
    # AgentSpansQueryReq's pydantic validator (which becomes a 422), so this
    # branch is defense-in-depth — but if it ever does fire we should map it
    # to a structured client error rather than letting ValueError bubble out.
    reserved = SPAN_GROUP_RESULT_COLS.union(frozenset(group_aliases))
    collisions = sorted(
        {measure.alias for measure in measures if measure.alias in reserved}
    )
    if collisions:
        raise ValueError(
            f"measure aliases collide with grouped row fields: {collisions!r}"
        )


def group_filters_having_sql(
    pb: ParamBuilder,
    filters: list[AgentSpanGroupFilter],
    *,
    table_alias: str = "s",
) -> str:
    """Build HAVING conditions for grouped span aggregate filters."""
    conditions: list[str] = []
    for filter_ in filters:
        measure = span_measure_sql(filter_.measure, pb, table_alias=table_alias)
        expr = measure.aggregate_sql
        if filter_.min is not None:
            min_slot = _group_filter_bound_slot(pb, filter_.min, measure.value_type)
            conditions.append(f"{expr} >= {min_slot}")
        if filter_.max is not None:
            max_slot = _group_filter_bound_slot(pb, filter_.max, measure.value_type)
            conditions.append(f"{expr} <= {max_slot}")
    return " AND ".join(conditions)


def _group_filter_bound_slot(
    pb: ParamBuilder,
    value: float | datetime.datetime,
    measure_value_type: AgentSpanStatsColumnValueType,
) -> str:
    if isinstance(value, datetime.datetime):
        if measure_value_type != _VALUE_TYPE_DATETIME:
            raise ValueError("datetime group filter bounds require a datetime measure")
        return pb.add(value, param_type="DateTime64(6)")
    if measure_value_type == _VALUE_TYPE_DATETIME:
        raise ValueError("datetime measures require datetime group filter bounds")
    return pb.add(value, param_type="Float64")


# ---------------------------------------------------------------------------
# WHERE builders (private — shared between count + list variants)
# ---------------------------------------------------------------------------


def _optional_where_clause(where: str, *, prefix: str = " ") -> str:
    return f"{prefix}WHERE {where}" if where else ""


def _project_filter_sql(column_sql: str, project_slot: str) -> str:
    return f"{column_sql} = {project_slot}"


def _and_conditions(*conditions: str) -> str:
    return " AND ".join(condition for condition in conditions if condition)


def _spans_filter_sql(
    pb: ParamBuilder,
    req: AgentSpansQueryReq | AgentCustomAttrsSchemaReq,
) -> _FilterSQL:
    pid_slot = pb.add(req.project_id, param_type="String")
    where_conditions = [_project_filter_sql("s.project_id", pid_slot)]
    add_time_filters(
        where_conditions,
        pb,
        started_after=req.started_after,
        started_before=req.started_before,
    )
    if req.query is not None:
        # Imported lazily to avoid a circular import between this module
        # (used by agent_query_compiler) and the compiler itself.
        from weave.trace_server.query_builder import agent_query_compiler

        where_conditions.append(agent_query_compiler.compile_agent_query(req.query, pb))
    return _FilterSQL(where=" AND ".join(where_conditions))


def _group_by_references_identity(group_by: list[AgentGroupByRef] | None) -> bool:
    """Whether any field/column group-by ref targets an identity column."""
    if not group_by:
        return False
    field_keys = [ref.key for ref in group_by if ref.source in _FIELD_GROUP_BY_SOURCES]
    return agent_trace_attribution.fields_reference_identity(field_keys)


def _spans_query_references_identity(req: AgentSpansQueryReq) -> bool:
    """Whether a spans query filters or groups by a trace-attributed column."""
    return agent_trace_attribution.query_references_identity(
        req.query
    ) or _group_by_references_identity(req.group_by)


def _spans_source(
    pb: ParamBuilder,
    req: AgentSpansQueryReq,
    *,
    attribute: bool,
    include_costs: bool = False,
) -> str:
    """Return the FROM source for a spans query.

    The base relation is the raw `spans` table, or the cost-augmented source
    (per-span price JOIN) when `include_costs` is set so cost columns are
    available downstream. When `attribute` is set, that base is wrapped so the
    four identity columns inherit from their trace when unset (see
    `agent_trace_attribution`); otherwise the base is used directly so
    non-identity queries skip the extra trace scan.
    """
    base = cost_augmented_source_sql(pb, req.project_id) if include_costs else "spans"
    if not attribute:
        return base
    return agent_trace_attribution.attributed_spans_source(
        pb,
        project_id=req.project_id,
        started_after=req.started_after,
        started_before=req.started_before,
        base_relation=base,
    )


def _agents_where(pb: ParamBuilder, req: AgentsQueryReq) -> str:
    conditions: list[str] = []
    if req.filters and req.filters.agent_name:
        aname_slot = pb.add(req.filters.agent_name, param_type="String")
        conditions.append(f"agent_name = {aname_slot}")
    return " AND ".join(conditions)


def _normalize_search_roles(roles: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for role in roles:
        if role == "tool":
            normalized.extend(["tool_call", "tool_result"])
        else:
            normalized.append(role)
    return list(dict.fromkeys(normalized))


def _escape_like_pattern(value: str) -> str:
    """Escape LIKE wildcards while keeping the surrounding substring match."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _search_filter_sql(pb: ParamBuilder, req: AgentSearchReq) -> _FilterSQL:
    """Build WHERE filters for a search against the messages table."""
    pid_slot = pb.add(req.project_id, param_type="String")
    conditions = [_project_filter_sql("project_id", pid_slot)]
    if req.query:
        content_slot = pb.add(
            f"%{_escape_like_pattern(req.query)}%", param_type="String"
        )
        conditions.append(f"content LIKE {content_slot}")
    if req.trace_id:
        trace_slot = pb.add(req.trace_id, param_type="String")
        conditions.append(f"trace_id = {trace_slot}")
    if req.roles:
        roles_slot = pb.add(
            _normalize_search_roles(req.roles), param_type="Array(String)"
        )
        conditions.append(f"role IN {roles_slot}")
    if req.agent_name:
        agent_slot = pb.add(req.agent_name, param_type="String")
        conditions.append(f"agent_name = {agent_slot}")
    if req.provider_name:
        provider_slot = pb.add(req.provider_name, param_type="String")
        conditions.append(f"provider_name = {provider_slot}")
    if req.request_model:
        model_slot = pb.add(req.request_model, param_type="String")
        conditions.append(f"request_model = {model_slot}")
    if req.conversation_id:
        conv_slot = pb.add(req.conversation_id, param_type="String")
        conditions.append(f"conversation_id = {conv_slot}")
    if req.started_after:
        after_slot = pb.add(req.started_after, param_type="DateTime64(6)")
        conditions.append(f"started_at >= {after_slot}")
    if req.started_before:
        before_slot = pb.add(req.started_before, param_type="DateTime64(6)")
        conditions.append(f"started_at < {before_slot}")
    return _FilterSQL(where=" AND ".join(conditions))


# ---------------------------------------------------------------------------
# Spans queries (ungrouped + grouped share the same entry points)
# ---------------------------------------------------------------------------


# Aggregate SELECT list shared between grouped list queries.
# The bundle is intentionally fixed because callers do not pick aggregates.
# Fields that map to specific UI pivots (invocation_count, conversation_names)
# are included alongside cross-cutting totals so all group_by shapes return the
# same schema.
_GROUPED_SPAN_AGGREGATES: str = """count() AS span_count,
               countIf(s.operation_name = 'invoke_agent') AS invocation_count,
               uniq(s.conversation_id) AS conversation_count,
               sum(s.input_tokens) AS total_input_tokens,
               sum(s.cache_creation_input_tokens) AS total_cache_creation_input_tokens,
               sum(s.cache_read_input_tokens) AS total_cache_read_input_tokens,
               sum(s.output_tokens) AS total_output_tokens,
               sum(s.reasoning_tokens) AS total_reasoning_tokens,
               sum(toUnixTimestamp64Milli(s.ended_at) - toUnixTimestamp64Milli(s.started_at)) AS total_duration_ms,
               countIf(s.status_code = 'ERROR') AS error_count,
               groupUniqArray(s.agent_name) AS agent_names,
               groupUniqArray(s.agent_version) AS agent_versions,
               groupUniqArray(s.provider_name) AS provider_names,
               groupUniqArray(s.request_model) AS request_models,
               groupUniqArray(s.conversation_name) AS conversation_names,
               min(s.started_at) AS first_seen,
               max(s.started_at) AS last_seen"""


def make_spans_count_query(pb: ParamBuilder, req: AgentSpansQueryReq) -> str:
    """Count spans matching the request, or count of distinct groups if grouped."""
    # Count only needs trace attribution when identity participates in matching
    # or grouping; otherwise the raw table avoids the extra trace scan. The
    # attributed source is allocated last (see `_spans_source`) so it never
    # renumbers the filter / group params.
    attribute = _spans_query_references_identity(req)
    span_filters = _spans_filter_sql(pb, req)
    if not req.group_by:
        source = _spans_source(pb, req, attribute=attribute)
        return f"SELECT count() FROM {source} s WHERE {span_filters.where}"
    resolved = resolve_group_by(pb, req.group_by)
    aliases = [alias for _, alias in resolved]
    _ensure_group_measure_aliases_do_not_collide(aliases, req.measures)
    group_exprs = ", ".join(expr for expr, _ in resolved)
    group_filters = span_group_filters(
        req.group_filters,
        default_group_by=req.group_by,
    )
    ensure_group_filters_match(group_filters, req.group_by, context="spans count")
    having = group_filters_having_sql(pb, group_filters)
    having_sql = f" HAVING {having}" if having else ""
    source = _spans_source(pb, req, attribute=attribute)
    return (
        f"SELECT count() FROM ("
        f"SELECT {group_exprs} FROM {source} s WHERE {span_filters.where} "
        f"GROUP BY {group_exprs}"
        f"{having_sql}"
        f")"
    )


def make_spans_list_query(pb: ParamBuilder, req: AgentSpansQueryReq) -> str:
    """List spans (ungrouped) or aggregate groups (grouped)."""
    # Always attribute: the spans table and its grouped rollups exist to show
    # each span's agent / conversation identity, which child spans only have via
    # their trace. The attributed source is allocated last (see `_spans_source`)
    # so it never renumbers the filter / projection params.
    span_filters = _spans_filter_sql(pb, req)
    limit_slot, offset_slot = _pagination_slots(pb, req.limit, req.offset)

    if not req.group_by:
        custom_sort_exprs = _custom_attr_sort_exprs(pb, req.custom_attr_columns)
        sortable = SPAN_SORTABLE_COLS.union(frozenset(custom_sort_exprs.keys()))
        if req.include_costs:
            sortable = sortable.union(_SPAN_COST_SORTABLE_COLS)
        order_by = build_order_by(
            req.sort_by,
            sortable,
            "started_at DESC",
            column_exprs=custom_sort_exprs,
        )
        custom_attr_projection = _custom_attr_map_projection(
            pb, req.custom_attr_columns
        )
        details_projection = f", {SPANS_DETAILS_COLS}" if req.include_details else ""
        cost_projection = f", {SPANS_COST_COLS}" if req.include_costs else ""
        source = _spans_source(pb, req, attribute=True, include_costs=req.include_costs)
        return f"""
            SELECT {SPANS_LIST_COLS}{details_projection}{custom_attr_projection}{cost_projection}
            FROM {source} s
            WHERE {span_filters.where}
            ORDER BY {order_by}
            LIMIT {limit_slot} OFFSET {offset_slot}
        """

    resolved = resolve_group_by(pb, req.group_by)
    aliases = [a for _, a in resolved]
    _ensure_group_measure_aliases_do_not_collide(aliases, req.measures)
    select_group_cols = ", ".join(f"{expr} AS {alias}" for expr, alias in resolved)
    group_by_clause = ", ".join(aliases)

    measure_sqls = [span_measure_sql(measure, pb) for measure in req.measures]
    dynamic_aggregate_selects = ",\n               ".join(
        f"{measure.aggregate_sql} AS {measure.alias}" for measure in measure_sqls
    )
    aggregate_selects = _GROUPED_SPAN_AGGREGATES
    if dynamic_aggregate_selects:
        aggregate_selects = (
            f"{aggregate_selects},\n               {dynamic_aggregate_selects}"
        )
    if req.include_costs:
        aggregate_selects = (
            f"{aggregate_selects},\n"
            "               sum(s.total_cost_usd) AS total_cost_usd,\n"
            "               sum(s.input_cost_usd) AS total_input_cost_usd,\n"
            "               sum(s.output_cost_usd) AS total_output_cost_usd"
        )
    sortable = SPAN_GROUP_AGGREGATE_COLS.union(frozenset(aliases)).union(
        measure.alias for measure in measure_sqls
    )
    if req.include_costs:
        sortable = sortable.union(frozenset(GROUPED_COST_ALIASES))
    default_order_by = (
        f"{measure_sqls[0].alias} DESC" if measure_sqls else "last_seen DESC"
    )
    order_by = build_order_by(req.sort_by, sortable, default_order_by)
    group_filters = span_group_filters(
        req.group_filters,
        default_group_by=req.group_by,
    )
    ensure_group_filters_match(group_filters, req.group_by, context="spans list")
    having = group_filters_having_sql(pb, group_filters)
    having_sql = f"HAVING {having}" if having else ""
    source = _spans_source(pb, req, attribute=True, include_costs=req.include_costs)

    return f"""
        SELECT {select_group_cols},
               {aggregate_selects}
        FROM {source} s
        WHERE {span_filters.where}
        GROUP BY {group_by_clause}
        {having_sql}
        ORDER BY {order_by}
        LIMIT {limit_slot} OFFSET {offset_slot}
    """


def make_conversation_previews_query(
    pb: ParamBuilder,
    project_id: str,
    conversation_ids: Collection[str],
    *,
    started_after: datetime.datetime | None = None,
    started_before: datetime.datetime | None = None,
) -> str:
    """First/last message previews for an explicit set of conversations.

    Deliberately scoped to ``conversation_id IN (...)`` — the page's already
    computed conversation_ids — so the wide ``input_messages`` / ``output_messages``
    columns are only read for the conversations actually shown, not for every
    span matching the list filters. (A grouped ``argMin``/``argMax`` folded into
    the main list query would read those columns for the entire filter match
    before LIMIT.) The bloom-filter skip index on ``conversation_id`` plus the
    optional time range bound the scan further.

    ``argMinIf``/``argMaxIf`` pick the earliest input and latest output span that
    actually carries messages; the handler turns the arrays into preview text.
    """
    pid_slot = pb.add(project_id, param_type="String")
    ids_slot = pb.add(list(conversation_ids), param_type="Array(String)")
    where_conditions = [
        _project_filter_sql("s.project_id", pid_slot),
        f"s.conversation_id IN {ids_slot}",
    ]
    add_time_filters(
        where_conditions,
        pb,
        started_after=started_after,
        started_before=started_before,
    )
    where = " AND ".join(where_conditions)
    return f"""
        SELECT s.conversation_id AS conversation_id,
               argMinIf(s.input_messages, s.started_at, length(s.input_messages) > 0) AS first_input_messages,
               argMaxIf(s.output_messages, s.ended_at, length(s.output_messages) > 0) AS last_output_messages
        FROM spans s
        WHERE {where}
        GROUP BY conversation_id
    """


def make_custom_attrs_schema_query(
    pb: ParamBuilder, req: AgentCustomAttrsSchemaReq
) -> str:
    """Discover typed custom attribute keys for spans matching the request.

    The query intentionally unnests only Map keys. Values can be arbitrarily
    large, and callers only need the typed source to build follow-up
    filter/group/stats requests.
    """
    span_filters = _spans_filter_sql(pb, req)
    limit_slot = pb.add(req.limit + 1, param_type="UInt64")
    offset_slot = pb.add(req.offset, param_type="UInt64")
    key_columns = ",\n               ".join(
        f"s.{source}.keys AS {source}_keys" for source, _ in _CUSTOM_ATTR_SCHEMA_SOURCES
    )
    attr_arrays = ",\n            ".join(
        f"arrayMap(k -> tuple('{source}', k, '{value_type}'), filtered.{source}_keys)"
        for source, value_type in _CUSTOM_ATTR_SCHEMA_SOURCES
    )
    return f"""
        SELECT tupleElement(attr, 1) AS source,
               tupleElement(attr, 2) AS key,
               tupleElement(attr, 3) AS value_type,
               count() AS span_count
        FROM (
            SELECT {key_columns}
            FROM spans s
            WHERE {span_filters.where}
        ) filtered
        ARRAY JOIN arrayConcat(
            {attr_arrays}
        ) AS attr
        GROUP BY source, key, value_type
        ORDER BY span_count DESC, key ASC, source ASC
        LIMIT {limit_slot} OFFSET {offset_slot}
    """


def span_group_distribution_key(value: SpanGroupKeyValue) -> str:
    """Call `str(value)` or return an empty string for None."""
    return "" if value is None else str(value)


def _span_group_distribution_context(
    pb: ParamBuilder,
    req: AgentSpansQueryReq,
    group_values: Sequence[SpanGroupKeyValue],
) -> SpanGroupDistributionContext:
    if not req.group_by or len(req.group_by) != 1:
        raise ValueError("span group distributions require exactly one group_by ref")
    group_expr, _ = resolve_group_by(pb, req.group_by)[0]
    group_key_sql = f"toString({group_expr})"
    group_values_slot = pb.add(
        [span_group_distribution_key(value) for value in group_values],
        param_type="Array(String)",
    )
    return SpanGroupDistributionContext(
        group_key_sql=group_key_sql,
        group_values_slot=group_values_slot,
    )


def _span_group_distribution_spec_tuple_sql(
    pb: ParamBuilder,
    spec: AgentSpanGroupDistributionSpec,
    *,
    limit_value: int,
) -> str:
    alias_slot = pb.add(spec.alias, param_type="String")
    source_slot = pb.add(spec.value.source, param_type="String")
    key_slot = pb.add(spec.value.key, param_type="String")
    limit_slot = pb.add(limit_value, param_type="UInt64")
    return f"tuple({alias_slot}, {source_slot}, {key_slot}, {limit_slot})"


def _span_group_distribution_specs_array_sql(
    pb: ParamBuilder,
    specs: Sequence[AgentSpanGroupDistributionSpec],
    *,
    get_limit: Callable[[AgentSpanGroupDistributionSpec], int],
) -> str:
    spec_tuples = [
        _span_group_distribution_spec_tuple_sql(pb, spec, limit_value=get_limit(spec))
        for spec in specs
    ]
    return f"array({', '.join(spec_tuples)})"


def make_span_group_distribution_counts_query(
    pb: ParamBuilder,
    req: AgentSpansQueryReq,
    group_values: Sequence[SpanGroupKeyValue],
) -> str:
    """Count filtered spans per returned group row."""
    span_filters = _spans_filter_sql(pb, req)
    context = _span_group_distribution_context(pb, req, group_values)
    source = _spans_source(pb, req, attribute=_spans_query_references_identity(req))
    return f"""
        SELECT {context.group_key_sql} AS group_key,
               count() AS total_count
        FROM {source} s
        WHERE {span_filters.where}
          AND {context.group_key_sql} IN {context.group_values_slot}
        GROUP BY group_key
    """


def make_span_group_numeric_distributions_query(
    pb: ParamBuilder,
    req: AgentSpansQueryReq,
    group_values: Sequence[SpanGroupKeyValue],
    specs: Sequence[AgentSpanGroupDistributionSpec],
) -> str:
    """Build per-group histograms for numeric custom attributes."""
    numeric_specs = [
        spec for spec in specs if spec.value.source in _NUMERIC_DISTRIBUTION_SOURCES
    ]
    if not numeric_specs:
        raise ValueError("numeric span group distributions require numeric specs")
    span_filters = _spans_filter_sql(pb, req)
    context = _span_group_distribution_context(pb, req, group_values)
    specs_sql = _span_group_distribution_specs_array_sql(
        pb,
        numeric_specs,
        get_limit=lambda spec: spec.bins,
    )
    source = _spans_source(pb, req, attribute=_spans_query_references_identity(req))
    spec_alias_sql = "tupleElement(spec, 1)"
    spec_source_sql = "tupleElement(spec, 2)"
    spec_key_sql = "tupleElement(spec, 3)"
    spec_bins_sql = "tupleElement(spec, 4)"
    map_contains_sql = (
        f"multiIf({spec_source_sql} = '{_SOURCE_CUSTOM_ATTRS_INT}', "
        f"mapContains(s.{_SOURCE_CUSTOM_ATTRS_INT}, {spec_key_sql}), "
        f"{spec_source_sql} = '{_SOURCE_CUSTOM_ATTRS_FLOAT}', "
        f"mapContains(s.{_SOURCE_CUSTOM_ATTRS_FLOAT}, {spec_key_sql}), "
        "false)"
    )
    value_sql = (
        f"multiIf({spec_source_sql} = '{_SOURCE_CUSTOM_ATTRS_INT}', "
        f"toFloat64(s.{_SOURCE_CUSTOM_ATTRS_INT}[{spec_key_sql}]), "
        f"{spec_source_sql} = '{_SOURCE_CUSTOM_ATTRS_FLOAT}', "
        f"toFloat64(s.{_SOURCE_CUSTOM_ATTRS_FLOAT}[{spec_key_sql}]), "
        "NULL)"
    )
    bucket_width_sql = (
        "if(bounds.max_value > bounds.min_value, "
        "(bounds.max_value - bounds.min_value) / toFloat64(bounds.bins), 1.0)"
    )
    bucket_index_sql = (
        "if(bounds.max_value = bounds.min_value, toUInt64(0), "
        "toUInt64(least(toFloat64(bounds.bins) - 1.0, floor("
        f"(value_rows.value - bounds.min_value) / {bucket_width_sql}))))"
    )
    bucket_min_sql = (
        "if(bounds.max_value = bounds.min_value, bounds.min_value, "
        f"bounds.min_value + toFloat64(all_buckets.bucket_index) * "
        f"{bucket_width_sql})"
    )
    bucket_max_sql = (
        "if(bounds.max_value = bounds.min_value, bounds.max_value, "
        "if(all_buckets.bucket_index = bounds.bins - toUInt64(1), "
        "bounds.max_value, "
        "bounds.min_value + toFloat64(all_buckets.bucket_index + 1) * "
        f"{bucket_width_sql}))"
    )
    return f"""
        WITH
          value_rows AS (
            SELECT group_key,
                   alias,
                   bins,
                   value
            FROM (
              SELECT {context.group_key_sql} AS group_key,
                     {spec_alias_sql} AS alias,
                     {spec_bins_sql} AS bins,
                     {value_sql} AS value
              FROM {source} s
              ARRAY JOIN {specs_sql} AS spec
              WHERE {span_filters.where}
                AND {context.group_key_sql} IN {context.group_values_slot}
                AND {map_contains_sql}
            )
            WHERE isNotNull(value)
              AND isFinite(value)
          ),
          bounds AS (
            SELECT group_key,
                   alias,
                   bins,
                   min(value) AS min_value,
                   max(value) AS max_value,
                   count() AS present_count
            FROM value_rows
            GROUP BY group_key, alias, bins
          ),
          all_buckets AS (
            SELECT group_key,
                   alias,
                   bins,
                   toUInt64(bucket_index) AS bucket_index
            FROM bounds
            ARRAY JOIN range(bins) AS bucket_index
          ),
          aggregated AS (
            SELECT value_rows.group_key AS group_key,
                   value_rows.alias AS alias,
                   {bucket_index_sql} AS bucket_index,
                   count() AS bin_count
            FROM value_rows
            INNER JOIN bounds
              ON value_rows.group_key = bounds.group_key
             AND value_rows.alias = bounds.alias
            GROUP BY group_key, alias, bucket_index
          )
        SELECT bounds.group_key AS group_key,
               bounds.alias AS alias,
               all_buckets.bucket_index AS bucket_index,
               {bucket_min_sql} AS bucket_min,
               {bucket_max_sql} AS bucket_max,
               ifNull(aggregated.bin_count, 0) AS count,
               bounds.present_count AS present_count
        FROM bounds
        INNER JOIN all_buckets
          ON all_buckets.group_key = bounds.group_key
         AND all_buckets.alias = bounds.alias
        LEFT JOIN aggregated
          ON aggregated.group_key = bounds.group_key
         AND aggregated.alias = bounds.alias
         AND aggregated.bucket_index = all_buckets.bucket_index
        WHERE bounds.present_count > 0
          AND (
            bounds.max_value > bounds.min_value
            OR all_buckets.bucket_index = 0
          )
        ORDER BY group_key ASC, alias ASC, bucket_index ASC
    """


def make_span_group_categorical_distributions_query(
    pb: ParamBuilder,
    req: AgentSpansQueryReq,
    group_values: Sequence[SpanGroupKeyValue],
    specs: Sequence[AgentSpanGroupDistributionSpec],
) -> str:
    """Build per-group top value counts for categorical custom attrs."""
    categorical_specs = [
        spec for spec in specs if spec.value.source in _CATEGORICAL_DISTRIBUTION_SOURCES
    ]
    if not categorical_specs:
        raise ValueError(
            "categorical span group distributions require categorical specs"
        )
    span_filters = _spans_filter_sql(pb, req)
    context = _span_group_distribution_context(pb, req, group_values)
    specs_sql = _span_group_distribution_specs_array_sql(
        pb,
        categorical_specs,
        get_limit=lambda spec: spec.top_n,
    )
    source = _spans_source(pb, req, attribute=_spans_query_references_identity(req))
    spec_alias_sql = "tupleElement(spec, 1)"
    spec_source_sql = "tupleElement(spec, 2)"
    spec_key_sql = "tupleElement(spec, 3)"
    spec_top_n_sql = "tupleElement(spec, 4)"
    map_contains_sql = (
        f"multiIf({spec_source_sql} = '{_SOURCE_CUSTOM_ATTRS_STRING}', "
        f"mapContains(s.{_SOURCE_CUSTOM_ATTRS_STRING}, {spec_key_sql}), "
        f"{spec_source_sql} = '{_SOURCE_CUSTOM_ATTRS_BOOL}', "
        f"mapContains(s.{_SOURCE_CUSTOM_ATTRS_BOOL}, {spec_key_sql}), "
        "false)"
    )
    value_sql = (
        f"multiIf({spec_source_sql} = '{_SOURCE_CUSTOM_ATTRS_BOOL}', "
        f"if(s.{_SOURCE_CUSTOM_ATTRS_BOOL}[{spec_key_sql}] = 1, 'true', 'false'), "
        f"{spec_source_sql} = '{_SOURCE_CUSTOM_ATTRS_STRING}', "
        f"toString(s.{_SOURCE_CUSTOM_ATTRS_STRING}[{spec_key_sql}]), "
        "''"
        ")"
    )
    return f"""
        WITH
          value_counts AS (
            SELECT group_key,
                   alias,
                   raw_value,
                   top_n,
                   count() AS value_count
            FROM (
              SELECT {context.group_key_sql} AS group_key,
                     {spec_alias_sql} AS alias,
                     {spec_top_n_sql} AS top_n,
                     {value_sql} AS raw_value
              FROM {source} s
              ARRAY JOIN {specs_sql} AS spec
              WHERE {span_filters.where}
                AND {context.group_key_sql} IN {context.group_values_slot}
                AND {map_contains_sql}
            )
            GROUP BY group_key, alias, raw_value, top_n
          ),
          ranked AS (
            SELECT group_key,
                   alias,
                   raw_value,
                   top_n,
                   value_count,
                   sum(value_count) OVER (
                     PARTITION BY group_key, alias
                   ) AS present_count,
                   row_number() OVER (
                     PARTITION BY group_key, alias
                     ORDER BY value_count DESC, raw_value ASC
                   ) AS value_rank
            FROM value_counts
          )
        SELECT group_key,
               alias,
               substring(raw_value, 1, 256) AS value,
               value_count AS count,
               present_count
        FROM ranked
        WHERE value_rank <= top_n
        ORDER BY group_key ASC, alias ASC, count DESC, raw_value ASC
    """


def make_trace_detail_spans_query(
    pb: ParamBuilder, project_id: str, trace_id: str
) -> str:
    """Fetch all spans for a single trace with chat-view projection.

    Internal helper for the chat view; not exposed as a public endpoint.
    Use `make_spans_list_query` with a `trace_id` filter for general
    span listings.
    """
    pid = pb.add(project_id, param_type="String")
    tid = pb.add(trace_id, param_type="String")
    # Always cost-augmented: the chat/detail views render per-message and
    # per-trace cost, and this is a single-trace fetch so the price JOIN is cheap.
    source = cost_augmented_source_sql(pb, project_id)
    return f"""
        SELECT {CHAT_VIEW_COLS}, {SPANS_COST_COLS} FROM {source} s
        WHERE {_project_filter_sql("s.project_id", pid)}
          AND s.trace_id = {tid}
        ORDER BY s.started_at ASC
    """


def make_spans_existence_query(
    pb: ParamBuilder,
    project_id: str,
    span_keys: Sequence[tuple[str, str]],
) -> str:
    """Batch existence + cached-field fetch for spans by (trace_id, span_id).

    Returns ``trace_id, span_id, span_name, started_at`` for each span that
    exists in the project. The ``spans`` table is ``ReplacingMergeTree(created_at)``
    so we collapse versions with ``GROUP BY (project_id, trace_id, span_id)`` +
    ``argMax(col, created_at)`` (never FINAL).

    ``span_keys`` is a list of ``(trace_id, span_id)`` tuples. We filter on the
    ``trace_id IN (...)`` and ``span_id IN (...)`` supersets (both bloom-indexed)
    and let the caller match exact pairs — the candidate set is bounded by the
    request size.

    Aggregate column references are qualified with the ``spans`` table name so
    the ``AS span_name`` / ``AS started_at`` output aliases cannot shadow the
    raw columns inside the aggregate arguments (ClickHouse would otherwise risk
    ILLEGAL_AGGREGATION) — same defensive pattern as the dataset_sources reads.
    """
    pid = pb.add(project_id, param_type="String")
    trace_ids = sorted({tid for tid, _ in span_keys})
    span_ids = sorted({sid for _, sid in span_keys})
    trace_ids_slot = pb.add(trace_ids, param_type="Array(String)")
    span_ids_slot = pb.add(span_ids, param_type="Array(String)")
    return f"""
        SELECT
            trace_id,
            span_id,
            argMax(spans.span_name, spans.created_at) AS span_name,
            argMax(spans.started_at, spans.created_at) AS started_at
        FROM spans
        WHERE project_id = {pid}
          AND trace_id IN {trace_ids_slot}
          AND span_id IN {span_ids_slot}
        GROUP BY project_id, trace_id, span_id
    """


# ---------------------------------------------------------------------------
# AMT-backed queries (agents, agent_versions)
# ---------------------------------------------------------------------------


def make_agents_count_query(pb: ParamBuilder, req: AgentsQueryReq) -> str:
    pid_slot = pb.add(req.project_id, param_type="String")
    where = _agents_where(pb, req)
    where_sql = _optional_where_clause(
        _and_conditions(_project_filter_sql("project_id", pid_slot), where)
    )
    return f"""SELECT count() FROM (
        SELECT agent_name FROM agents{where_sql} GROUP BY agent_name
    )"""


def make_agents_list_query(pb: ParamBuilder, req: AgentsQueryReq) -> str:
    pid_slot = pb.add(req.project_id, param_type="String")
    where = _agents_where(pb, req)
    where_sql = _optional_where_clause(
        _and_conditions(_project_filter_sql("project_id", pid_slot), where),
        prefix="\n        ",
    )
    order_by = build_order_by(
        req.sort_by, AGENT_SORTABLE_COLS, "last_seen DESC, agent_name"
    )
    limit_slot, offset_slot = _pagination_slots(pb, req.limit, req.offset)
    return f"""
        SELECT agent_name,
               sum(invocation_count) AS invocation_count,
               sum(span_count) AS span_count,
               sum(total_input_tokens) AS total_input_tokens,
               sum(total_output_tokens) AS total_output_tokens,
               sum(total_duration_ms) AS total_duration_ms,
               sum(error_count) AS error_count,
               min(first_seen) AS first_seen,
               max(last_seen) AS last_seen
        FROM agents
        {where_sql}
        GROUP BY agent_name
        ORDER BY {order_by}
        LIMIT {limit_slot} OFFSET {offset_slot}
    """


def make_agent_versions_count_query(
    pb: ParamBuilder, req: AgentVersionsQueryReq
) -> str:
    pid = pb.add(req.project_id, param_type="String")
    aname = pb.add(req.agent_name, param_type="String")
    return (
        f"SELECT count() FROM ("
        f"SELECT agent_version FROM agent_versions "
        f"WHERE {_project_filter_sql('project_id', pid)} AND agent_name = {aname} "
        f"GROUP BY agent_version"
        f")"
    )


def make_agent_versions_list_query(pb: ParamBuilder, req: AgentVersionsQueryReq) -> str:
    pid = pb.add(req.project_id, param_type="String")
    aname = pb.add(req.agent_name, param_type="String")
    limit_slot, offset_slot = _pagination_slots(pb, req.limit, req.offset)
    return f"""
        SELECT agent_version,
               sum(invocation_count) AS invocation_count,
               sum(span_count) AS span_count,
               sum(total_input_tokens) AS total_input_tokens,
               sum(total_output_tokens) AS total_output_tokens,
               sum(total_duration_ms) AS total_duration_ms,
               sum(error_count) AS error_count,
               min(first_seen) AS first_seen,
               max(last_seen) AS last_seen
        FROM agent_versions
        WHERE {_project_filter_sql("project_id", pid)}
          AND agent_name = {aname}
        GROUP BY agent_version
        ORDER BY last_seen DESC
        LIMIT {limit_slot} OFFSET {offset_slot}
    """


# ---------------------------------------------------------------------------
# Message search + chat spans
# ---------------------------------------------------------------------------


def make_message_search_query(pb: ParamBuilder, req: AgentSearchReq) -> str:
    """Search messages by content + span-level filters.

    Single-table scan against the `messages` table populated by an MV off
    `spans`. Content is stored inline (ClickHouse columnar compression
    handles repetition); `content_digest` is available for read-side dedup
    via GROUP BY when the caller wants unique content rather than unique
    occurrences.
    """
    filters = _search_filter_sql(pb, req)
    # Bounds (`0 <= limit <= MAX_SEARCH_LIMIT`, `offset >= 0`) are
    # enforced on AgentSearchReq.
    limit_slot = pb.add(req.limit, param_type="UInt64")
    offset_slot = pb.add(req.offset, param_type="UInt64")
    # Truncated preview keeps search-UI payloads small by default; full content
    # is for structured retrieval (e.g. agent scoring).
    content_expr = (
        f"substring(content, 1, {SEARCH_CONTENT_PREVIEW_CHARS})"
        if req.truncate_content
        else "content"
    )
    # content_digest is stored raw as FixedString(16); hex-encode here so
    # the Python API surface (AgentSearchMatchedMessage.content_digest: str)
    # keeps a portable text representation.
    return f"""
        SELECT conversation_id, conversation_name, agent_name,
               span_id, trace_id, role,
               {content_expr} AS content,
               lower(hex(content_digest)) AS content_digest, started_at
        FROM messages
        WHERE {filters.where}
        ORDER BY started_at DESC
        LIMIT {limit_slot} OFFSET {offset_slot}
    """


def make_conversation_chat_spans_query(
    pb: ParamBuilder, req: AgentConversationChatReq
) -> str:
    pid = pb.add(req.project_id, param_type="String")
    cid = pb.add(req.conversation_id, param_type="String")
    limit_slot = pb.add(req.limit, param_type="UInt64")
    offset_slot = pb.add(req.offset, param_type="UInt64")
    # Always cost-augmented so the multi-turn chat view can render per-message
    # and per-turn cost; bounded to one conversation's turns, so cheap.
    source = cost_augmented_source_sql(pb, req.project_id)
    return f"""
        SELECT {QUALIFIED_CHAT_VIEW_COLS}, {QUALIFIED_SPANS_COST_COLS}
        FROM {source} s
        INNER JOIN (
            SELECT trace_id, min(started_at) AS turn_started_at
            FROM spans
            WHERE {_project_filter_sql("project_id", pid)}
              AND conversation_id = {cid}
            GROUP BY trace_id
            ORDER BY turn_started_at DESC, trace_id DESC
            LIMIT {limit_slot} OFFSET {offset_slot}
        ) t ON s.trace_id = t.trace_id
        WHERE {_project_filter_sql("s.project_id", pid)}
        ORDER BY t.turn_started_at ASC, t.trace_id ASC, s.started_at ASC
    """


def make_conversation_chat_turns_count_query(
    pb: ParamBuilder, req: AgentConversationChatReq
) -> str:
    """Count distinct trace_id turns in a conversation."""
    pid = pb.add(req.project_id, param_type="String")
    cid = pb.add(req.conversation_id, param_type="String")
    return f"""
        SELECT count() FROM (
            SELECT trace_id
            FROM spans s
            WHERE {_project_filter_sql("s.project_id", pid)}
              AND s.conversation_id = {cid}
            GROUP BY trace_id
        )
    """


# ---------------------------------------------------------------------------
# Safe type coercion from query rows
# ---------------------------------------------------------------------------


def safe_int(val: Any) -> int:
    """Convert a value to int, defaulting to 0 for None/NULL."""
    if val is None:
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def safe_float(val: Any) -> float:
    """Convert a value to float, defaulting to 0.0 for None/NULL."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def safe_str(val: Any) -> str:
    """Convert a value to str, defaulting to '' for None/NULL."""
    if val is None:
        return ""
    return str(val)
