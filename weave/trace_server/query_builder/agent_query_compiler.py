"""Compile a `tsi.Query` expression into WHERE conditions for agent spans.

This is a lean port of the Query→SQL compiler from `calls_query_builder` —
the calls version is tightly coupled to feedback arrays, calls_complete
sentinels, and datetime-field coercions we don't want here. The Query AST
itself (`weave.trace_server.interface.query`) is reused verbatim.

Field-name resolution understands three sources, checked in order:

1. **Semconv keys.** Canonical `weave.*`, `gen_ai.*` alias, or prefix-
   stripped short form (`agent.name`) — all resolve to a span column via
   :data:`semconv.FILTERABLE_KEY_TO_COLUMN`.
2. **Direct span columns.** A small allowlist of column names not covered
   by semconv (`trace_id`, `started_at`, etc.).
3. **Custom attributes.** Everything else is treated as a custom attribute
   key. Three forms are accepted:

   - Explicit prefix: `custom_attrs_string.env` / `custom_attrs_int.retries` /
     `custom_attrs_float.latency_ms` force a specific map.
   - Unprefixed: the map is picked from the *sibling literal's Python type*
     in the enclosing comparison — `$eq(foo, 5)` reads `custom_attrs_int['foo']`,
     `$eq(foo, "x")` reads `custom_attrs_string['foo']`. Field-compared-to-field
     without a literal is rejected because there's no type signal.
"""

from __future__ import annotations

import re

from weave.trace_server.agents.semconv import FILTERABLE_KEY_TO_COLUMN
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import (
    ParamBuilder,
    clickhouse_cast,
    python_value_to_ch_type,
)

# Span columns queryable by their literal column name without a corresponding
# semconv key: OTel-core span identity and W&B plumbing. Columns that are the
# target of a semconv key (`agent_name`, `input_tokens`, etc.) are also
# accepted by column name; see `_ALL_QUERYABLE_COLUMNS`.
DIRECT_COLUMNS: frozenset[str] = frozenset(
    {
        "trace_id",
        "span_id",
        "parent_span_id",
        "span_name",
        "span_kind",
        "started_at",
        "ended_at",
        "status_code",
        "status_message",
        "wb_user_id",
        "wb_run_id",
    }
)

# Every column name the DSL will accept verbatim: OTel-core plus every column
# that some semconv key maps to.
_ALL_QUERYABLE_COLUMNS: frozenset[str] = DIRECT_COLUMNS.union(
    frozenset(FILTERABLE_KEY_TO_COLUMN.values())
)

# Field-name prefix -> Map column on the spans table. Longer prefixes must come
# before shorter ones: `custom_attrs_int.` has to be tried before
# `custom_attrs_string.` or every int field resolves to the string map.
_CUSTOM_ATTR_PREFIXES: dict[str, str] = {
    "custom_attrs_int.": "custom_attrs_int",
    "custom_attrs_float.": "custom_attrs_float",
    "custom_attrs_bool.": "custom_attrs_bool",
    "custom_attrs_string.": "custom_attrs_string",
}

# Python literal type -> custom attribute map when no explicit prefix is given.
# `bool` is a subclass of `int` in Python, but `dict.get(type(val))` uses
# exact-type lookup (not MRO), so `type(True)` finds `bool` first.
_LITERAL_TYPE_TO_MAP: dict[type, str] = {
    bool: "custom_attrs_bool",
    int: "custom_attrs_int",
    float: "custom_attrs_float",
    str: "custom_attrs_string",
}

_SQL_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class InvalidAgentFilterFieldError(ValueError):
    """Raised when a query DSL field can't be resolved to a column or attr."""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compile_agent_query(
    query: tsi_query.Query,
    pb: ParamBuilder,
    *,
    table_alias: str = "s",
) -> str:
    """Compile a `Query` into a WHERE condition.

    Callers AND the returned condition with their other filter clauses.
    The condition may contain internal `AND` / `OR` / `NOT`.
    """
    _validate_sql_identifier("table_alias", table_alias)
    return _compile_operation(query.expr_, pb, table_alias)


# ---------------------------------------------------------------------------
# Operation / operand compilation
# ---------------------------------------------------------------------------


def _compile_operation(
    op: tsi_query.Operation,
    pb: ParamBuilder,
    alias: str,
) -> str:
    if isinstance(op, tsi_query.AndOperation):
        if not op.and_:
            raise ValueError("Empty $and")
        if len(op.and_) == 1:
            return _compile_operand(op.and_[0], pb, alias)
        parts = [_compile_operand(p, pb, alias) for p in op.and_]
        return "(" + " AND ".join(parts) + ")"

    if isinstance(op, tsi_query.OrOperation):
        if not op.or_:
            raise ValueError("Empty $or")
        if len(op.or_) == 1:
            return _compile_operand(op.or_[0], pb, alias)
        parts = [_compile_operand(p, pb, alias) for p in op.or_]
        return "(" + " OR ".join(parts) + ")"

    if isinstance(op, tsi_query.NotOperation):
        if not op.not_:
            raise ValueError("Empty $not")
        inner = _compile_operand(op.not_[0], pb, alias)
        return f"(NOT ({inner}))"

    if isinstance(op, tsi_query.EqOperation):
        lhs, rhs = op.eq_
        lhs_sql, rhs_sql = _compile_comparison_operands(lhs, rhs, pb, alias)
        # $eq against a null literal -> IS NULL semantics
        if isinstance(rhs, tsi_query.LiteralOperation) and rhs.literal_ is None:
            return f"({lhs_sql} IS NULL)"
        if isinstance(lhs, tsi_query.LiteralOperation) and lhs.literal_ is None:
            return f"({rhs_sql} IS NULL)"
        return f"({lhs_sql} = {rhs_sql})"

    if isinstance(op, tsi_query.GtOperation):
        return _compile_non_null_comparison("$gt", op.gt_, ">", pb, alias)

    if isinstance(op, tsi_query.LtOperation):
        return _compile_non_null_comparison("$lt", op.lt_, "<", pb, alias)

    if isinstance(op, tsi_query.GteOperation):
        return _compile_non_null_comparison("$gte", op.gte_, ">=", pb, alias)

    if isinstance(op, tsi_query.LteOperation):
        return _compile_non_null_comparison("$lte", op.lte_, "<=", pb, alias)

    if isinstance(op, tsi_query.InOperation):
        field_operand, list_operand = op.in_
        if not list_operand:
            raise ValueError("Empty $in RHS list")
        hint = _common_literal_type("$in", list_operand)
        lhs_sql = _compile_operand(field_operand, pb, alias, sibling_hint=hint)
        rhs_parts = [_compile_operand(item, pb, alias) for item in list_operand]
        return f"({lhs_sql} IN ({', '.join(rhs_parts)}))"

    if isinstance(op, tsi_query.ContainsOperation):
        # $contains always compares strings — force sibling hint to str.
        lhs_sql = _compile_operand(op.contains_.input, pb, alias, sibling_hint=str)
        rhs_sql = _compile_operand(op.contains_.substr, pb, alias)
        fn = "positionCaseInsensitive" if op.contains_.case_insensitive else "position"
        return f"{fn}({lhs_sql}, {rhs_sql}) > 0"

    raise TypeError(f"Unknown operation type: {type(op).__name__}")


def _compile_operand(
    operand: tsi_query.Operand,
    pb: ParamBuilder,
    alias: str,
    *,
    sibling_hint: type | None = None,
) -> str:
    if isinstance(operand, tsi_query.LiteralOperation):
        value = operand.literal_
        if value is None:
            # Handled by callers that check for null explicitly; if we got
            # here it's being used as a scalar — emit NULL.
            return "NULL"
        slot = pb.add(value, param_type=python_value_to_ch_type(value))
        return slot

    if isinstance(operand, tsi_query.GetFieldOperator):
        return _resolve_field(operand.get_field_, pb, alias, sibling_hint=sibling_hint)

    if isinstance(operand, tsi_query.ConvertOperation):
        # The inner field resolution needs a sibling hint that matches the
        # cast target — `to: "int"` means pull from custom_attrs_int;
        # `to: "double"` means custom_attrs_float; otherwise String.
        cast_hint = _CAST_TO_TYPE.get(operand.convert_.to, str)
        inner_sql = _compile_operand(
            operand.convert_.input, pb, alias, sibling_hint=cast_hint
        )
        return clickhouse_cast(inner_sql, operand.convert_.to)

    if isinstance(
        operand,
        (
            tsi_query.AndOperation,
            tsi_query.OrOperation,
            tsi_query.NotOperation,
            tsi_query.EqOperation,
            tsi_query.GtOperation,
            tsi_query.LtOperation,
            tsi_query.GteOperation,
            tsi_query.LteOperation,
            tsi_query.InOperation,
            tsi_query.ContainsOperation,
        ),
    ):
        return _compile_operation(operand, pb, alias)

    raise TypeError(f"Unknown operand type: {type(operand).__name__}")


# `$convert` target type -> sibling hint for the inner field operand so
# `$convert(field=foo, to=int)` picks custom_attrs_int.
_CAST_TO_TYPE: dict[str, type] = {
    "int": int,
    "double": float,
    "bool": bool,
    "string": str,
    "exists": str,  # arbitrary; exists just checks NOT NULL
}


# ---------------------------------------------------------------------------
# Field resolution
# ---------------------------------------------------------------------------


def _resolve_field(
    name: str,
    pb: ParamBuilder,
    alias: str,
    *,
    sibling_hint: type | None,
) -> str:
    """Resolve a dotted field name to a SQL expression over the spans row."""
    _validate_sql_identifier("table alias", alias)

    # (1) Semconv key / alias / short-form
    col = FILTERABLE_KEY_TO_COLUMN.get(name)
    if col is not None:
        return f"{alias}.{col}"

    # (2) Direct column name — OTel-core plus any semconv target column
    if name in _ALL_QUERYABLE_COLUMNS:
        return f"{alias}.{name}"

    # (3a) Explicit custom_attrs_string prefix — user-chosen map wins over sibling type
    for prefix, map_col in _CUSTOM_ATTR_PREFIXES.items():
        if name.startswith(prefix):
            key = name[len(prefix) :]
            if not key:
                raise InvalidAgentFilterFieldError(
                    f"empty key after {prefix!r} in field name {name!r}"
                )
            key_slot = pb.add(key, param_type="String")
            return f"{alias}.{map_col}[{key_slot}]"

    # (3b) Unprefixed custom attr — pick map from sibling literal type
    if sibling_hint is None:
        raise InvalidAgentFilterFieldError(
            f"cannot resolve field {name!r}: not a known column and no sibling "
            "literal to infer the custom attribute map from. Either add the column "
            "to semconv / DIRECT_COLUMNS or use an explicit prefix like "
            "'custom_attrs_string.<key>' / 'custom_attrs_int.<key>' / "
            "'custom_attrs_float.<key>' / 'custom_attrs_bool.<key>'."
        )
    inferred_map = _LITERAL_TYPE_TO_MAP.get(sibling_hint)
    if inferred_map is None:
        raise InvalidAgentFilterFieldError(
            f"cannot resolve field {name!r}: sibling literal type "
            f"{sibling_hint.__name__} has no custom attribute map."
        )
    key_slot = pb.add(name, param_type="String")
    return f"{alias}.{inferred_map}[{key_slot}]"


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------


def _compile_comparison_operands(
    lhs: tsi_query.Operand,
    rhs: tsi_query.Operand,
    pb: ParamBuilder,
    alias: str,
) -> tuple[str, str]:
    """Compile (lhs, rhs) with custom-attr sibling-type dispatch.

    Peeks at the operands so a `GetFieldOperator` on one side is resolved
    using the other side's literal type as the custom attribute map hint.
    """
    lhs_hint = _literal_python_type(rhs)
    rhs_hint = _literal_python_type(lhs)
    lhs_sql = _compile_operand(lhs, pb, alias, sibling_hint=lhs_hint)
    rhs_sql = _compile_operand(rhs, pb, alias, sibling_hint=rhs_hint)
    return lhs_sql, rhs_sql


def _compile_non_null_comparison(
    op_name: str,
    operands: tuple[tsi_query.Operand, tsi_query.Operand],
    operator: str,
    pb: ParamBuilder,
    alias: str,
) -> str:
    lhs, rhs = operands
    if _is_null_literal(lhs) or _is_null_literal(rhs):
        raise ValueError(f"Null values are not allowed for {op_name} comparisons")
    lhs_sql, rhs_sql = _compile_comparison_operands(lhs, rhs, pb, alias)
    return f"({lhs_sql} {operator} {rhs_sql})"


def _literal_python_type(operand: tsi_query.Operand) -> type | None:
    """If `operand` is a literal with a usable Python type, return that type."""
    if isinstance(operand, tsi_query.LiteralOperation):
        val = operand.literal_
        if val is None:
            return None
        # `bool` is a subclass of `int` in Python — check it first.
        if isinstance(val, bool):
            return bool
        if isinstance(val, int):
            return int
        if isinstance(val, float):
            return float
        if isinstance(val, str):
            return str
    if isinstance(operand, tsi_query.ConvertOperation):
        return _CAST_TO_TYPE.get(operand.convert_.to)
    return None


def _is_null_literal(operand: tsi_query.Operand) -> bool:
    return isinstance(operand, tsi_query.LiteralOperation) and operand.literal_ is None


def _common_literal_type(
    op_name: str, operands: list[tsi_query.Operand]
) -> type | None:
    literal_types: set[type] = set()
    for op in operands:
        if _is_null_literal(op):
            raise ValueError(f"Null values are not allowed in {op_name} lists")
        t = _literal_python_type(op)
        if t is not None:
            literal_types.add(t)
    if len(literal_types) > 1:
        type_names = ", ".join(sorted(t.__name__ for t in literal_types))
        raise ValueError(
            f"All literal values in {op_name} lists must have the same type, "
            f"got: {type_names}"
        )
    return next(iter(literal_types), None)


def _validate_sql_identifier(label: str, value: str) -> None:
    if not _SQL_IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Invalid SQL identifier for {label}: {value!r}")


# ---------------------------------------------------------------------------
# Module API
# ---------------------------------------------------------------------------


__all__ = [
    "DIRECT_COLUMNS",
    "InvalidAgentFilterFieldError",
    "compile_agent_query",
]
