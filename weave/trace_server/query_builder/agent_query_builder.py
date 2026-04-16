"""Shared query-building helpers for GenAI ClickHouse queries.

Uses the ParamBuilder abstraction for parameterized query construction.
"""

from __future__ import annotations

from typing import Any

from weave.trace_server.agent_types import AgentCustomAttrFilter, AgentSortBy
from weave.trace_server.orm import ParamBuilder

# ---------------------------------------------------------------------------
# Column whitelists — only these can appear in WHERE/ORDER BY/GROUP BY
# ---------------------------------------------------------------------------

#: Columns on spans that can be filtered with equality/IN
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

#: Columns on spans that can be sorted
SPAN_SORTABLE_COLS: frozenset[str] = SPAN_FILTERABLE_COLS | frozenset(
    {
        "started_at",
        "ended_at",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "reasoning_tokens",
    }
)

#: Allowed operators for custom attribute filters
_ATTR_OPS: dict[str, str] = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "lt": "<",
    "gte": ">=",
    "lte": "<=",
}


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
        if s.field in allowed and s.direction in {"asc", "desc"}:
            expr = column_exprs.get(s.field, s.field) if column_exprs else s.field
            parts.append(f"{expr} {s.direction}")
    return ", ".join(parts) if parts else default


def add_time_filters(
    conditions: list[str],
    pb: ParamBuilder,
    *,
    start: str | None,
    end: str | None,
    column: str = "s.started_at",
) -> None:
    """Add start/end time range conditions using parseDateTimeBestEffort."""
    if start:
        conditions.append(
            f"{column} >= parseDateTimeBestEffort({pb.add(str(start), param_type='String')})"
        )
    if end:
        conditions.append(
            f"{column} < parseDateTimeBestEffort({pb.add(str(end), param_type='String')})"
        )


def add_span_filters(
    conditions: list[str],
    pb: ParamBuilder,
    filters: Any,
    *,
    table_alias: str = "s",
) -> None:
    """Add validated equality filters. Only columns in SPAN_FILTERABLE_COLS are allowed."""
    for attr in SPAN_FILTERABLE_COLS:
        val = getattr(filters, attr, None)
        if val:
            conditions.append(
                f"{table_alias}.{attr} = {pb.add(val, param_type='String')}"
            )


def add_custom_attr_filters(
    conditions: list[str],
    pb: ParamBuilder,
    custom_filters: list[AgentCustomAttrFilter] | None,
    *,
    table_alias: str = "s",
) -> None:
    """Add custom_attrs Map(String, String) filters with parameterized values."""
    if not custom_filters:
        return
    for cf in custom_filters:
        op = _ATTR_OPS.get(cf.operator, "=")
        key_slot = pb.add(str(cf.attr_key), param_type="String")
        val_slot = pb.add(str(cf.value), param_type="String")
        conditions.append(f"{table_alias}.custom_attrs[{key_slot}] {op} {val_slot}")


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
