"""Shared query-building helpers for GenAI ClickHouse queries.

Provides validated, parameterized query construction to prevent SQL injection
and ensure consistency across all GenAI query endpoints.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Column whitelists — only these can appear in WHERE/ORDER BY/GROUP BY
# ---------------------------------------------------------------------------

#: Columns on genai_spans that can be filtered with equality/IN
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
    }
)

#: Columns on genai_spans that can be sorted
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

#: Dimensions for GROUP BY in stats queries
STATS_GROUP_BY_COLS: frozenset[str] = frozenset(
    {
        "operation_name",
        "provider_name",
        "agent_name",
        "agent_version",
        "request_model",
        "tool_name",
        "conversation_id",
        "status_code",
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


# ---------------------------------------------------------------------------
# Safe ORDER BY builder
# ---------------------------------------------------------------------------


def build_order_by(
    sort_by: list[Any] | None,
    allowed: frozenset[str],
    default: str,
) -> str:
    """Build a safe ORDER BY clause, rejecting unknown columns."""
    if not sort_by:
        return default
    parts: list[str] = []
    for s in sort_by:
        col = s.field if hasattr(s, "field") else s.get("field", "")
        direction = (
            s.direction if hasattr(s, "direction") else s.get("direction", "desc")
        )
        if col in allowed and direction in {"asc", "desc"}:
            parts.append(f"{col} {direction}")
    return ", ".join(parts) if parts else default


# ---------------------------------------------------------------------------
# Time range filter builder
# ---------------------------------------------------------------------------


def add_time_filters(
    conditions: list[str],
    parameters: dict[str, Any],
    *,
    start: str | None,
    end: str | None,
    column: str = "s.started_at",
    param_prefix: str = "t",
) -> None:
    """Add start/end time range conditions using parseDateTimeBestEffort.

    Uses parameterized String values — safe against injection.
    """
    if start:
        p = f"{param_prefix}_start"
        conditions.append(f"{column} >= parseDateTimeBestEffort({{{p}:String}})")
        parameters[p] = str(start)
    if end:
        p = f"{param_prefix}_end"
        conditions.append(f"{column} < parseDateTimeBestEffort({{{p}:String}})")
        parameters[p] = str(end)


# ---------------------------------------------------------------------------
# Simple equality filter builder (for span columns)
# ---------------------------------------------------------------------------


def add_span_filters(
    conditions: list[str],
    parameters: dict[str, Any],
    filters: Any,
    *,
    table_alias: str = "s",
) -> None:
    """Add validated equality filters from an AgentSpansQueryFilters-like object.

    Only columns in SPAN_FILTERABLE_COLS are allowed.
    """
    filter_fields = {
        "trace_id",
        "operation_name",
        "agent_name",
        "agent_version",
        "provider_name",
        "tool_name",
        "request_model",
        "conversation_id",
        "status_code",
    }
    for attr in filter_fields:
        val = getattr(filters, attr, None)
        if val:
            if attr not in SPAN_FILTERABLE_COLS:
                continue  # safety: skip unknown columns
            param = f"f_{attr}"
            conditions.append(f"{table_alias}.{attr} = {{{param}:String}}")
            parameters[param] = val


# ---------------------------------------------------------------------------
# Custom attrs (Map) filter builder
# ---------------------------------------------------------------------------


def add_custom_attr_filters(
    conditions: list[str],
    parameters: dict[str, Any],
    custom_filters: list[Any] | None,
    *,
    table_alias: str = "s",
) -> None:
    """Add custom_attrs Map(String, String) filters with parameterized values.

    All values are compared as strings. The attr_key and value are parameterized
    to prevent SQL injection.
    """
    if not custom_filters:
        return
    for i, cf in enumerate(custom_filters):
        key_param = f"cf{i}_key"
        val_param = f"cf{i}_val"
        attr_key = cf.attr_key if hasattr(cf, "attr_key") else cf.get("attr_key", "")
        value = cf.value if hasattr(cf, "value") else cf.get("value", "")
        operator = cf.operator if hasattr(cf, "operator") else cf.get("operator", "eq")

        op = _ATTR_OPS.get(operator, "=")
        parameters[key_param] = str(attr_key)
        parameters[val_param] = str(value)
        conditions.append(
            f"{table_alias}.custom_attrs[{{{key_param}:String}}] {op} {{{val_param}:String}}"
        )


# ---------------------------------------------------------------------------
# SummingMergeTree HAVING filter builder
# ---------------------------------------------------------------------------


def add_having_filters(
    having_conditions: list[str],
    parameters: dict[str, Any],
    filters: Any,
    *,
    string_cols: list[str],
    start_field: str | None = None,
    end_field: str | None = None,
) -> None:
    """Add HAVING conditions for SimpleAggregateFunction columns on MVs.

    Uses aliased column names from the SELECT (max(col) AS col).
    """
    for attr in string_cols:
        val = getattr(filters, attr, None)
        if val:
            param = f"h_{attr}"
            having_conditions.append(f"{attr} = {{{param}:String}}")
            parameters[param] = val

    if start_field:
        start_val = getattr(filters, start_field, None)
        if start_val:
            having_conditions.append(
                "last_seen >= parseDateTimeBestEffort({h_start:String})"
            )
            parameters["h_start"] = str(start_val)

    if end_field:
        end_val = getattr(filters, end_field, None)
        if end_val:
            having_conditions.append(
                "first_seen < parseDateTimeBestEffort({h_end:String})"
            )
            parameters["h_end"] = str(end_val)


# ---------------------------------------------------------------------------
# Stats GROUP BY builder
# ---------------------------------------------------------------------------


def build_group_by_clause(
    group_by: str | None,
    allowed: frozenset[str] = STATS_GROUP_BY_COLS,
    *,
    table_alias: str = "s",
) -> tuple[str, str, str]:
    """Build GROUP BY extension for stats queries.

    Returns (group_select_sql, group_by_extra, group_by_col).
    Only allowed columns can be used.
    """
    if not group_by or group_by not in allowed:
        return "", "", ""
    return (
        f", {table_alias}.{group_by} AS group_value",
        ", group_value",
        group_by,
    )


# ---------------------------------------------------------------------------
# Safe int/str extraction from query rows
# ---------------------------------------------------------------------------


def safe_int(val: Any) -> int:
    """Convert a ClickHouse value to int, defaulting to 0 for None/NULL."""
    if val is None:
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def safe_str(val: Any) -> str:
    """Convert a ClickHouse value to str, defaulting to '' for None/NULL."""
    if val is None:
        return ""
    return str(val)
