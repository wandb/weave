import contextlib
import logging
from collections.abc import Generator

import sqlparse

from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import (
    ParamBuilder,
    clickhouse_cast_json_value,
    quote_json_path_parts,
)
from weave.trace_server.project_version.types import ReadTable


def safe_alias(field_name: str) -> str:
    """Backtick-quote field names containing dots for use as SQL aliases."""
    return f"`{field_name}`" if "." in field_name else field_name


def param_slot(param_name: str, param_type: str) -> str:
    """Helper function to create a parameter slot for a clickhouse query."""
    return f"{{{param_name}:{param_type}}}"


def trace_id_index_expr(trace_id_sql: str, read_table: ReadTable) -> str:
    """Wrap `trace_id_sql` to match the table's trace_id index expression.

    Migration 031 builds `idx_trace_id_bloom` on `ifNull(trace_id, '')` because
    `calls_merged.trace_id` is `SimpleAggregateFunction(any, Nullable(String))`
    and a bloom filter on a Nullable column is not pruned by direct equality.
    Predicates must match the index expression character-for-character to enable
    granule pruning. On `calls_complete`, `trace_id` is non-nullable `String`
    with an index on the raw column, so the raw expression is used.
    """
    if read_table == ReadTable.CALLS_MERGED:
        return f"ifNull({trace_id_sql}, '')"
    if read_table == ReadTable.CALLS_COMPLETE:
        return trace_id_sql
    raise ValueError(f"Unhandled read_table: {read_table}")


def safely_format_sql(
    sql: str,
    logger: logging.Logger,
) -> str:
    """Safely format a SQL string with parameters."""
    try:
        return sqlparse.format(sql, reindent=True)
    except:
        logger.info("Failed to format SQL: %s", sql)
        return sql


# Context for tracking if we're in a NOT operation
class NotContext:
    # Nesting depth
    _depth = 0

    @classmethod
    @contextlib.contextmanager
    def not_context(cls) -> Generator[None, None, None]:
        """Context manager for NOT operations.

        Properly handles nested NOT operations by tracking depth.
        In boolean logic:
        - NOT(expr) flips the result
        - NOT(NOT(expr)) is equivalent to expr
        - NOT(NOT(NOT(expr))) is equivalent to NOT(expr)

        So we only apply special handling when nesting depth is odd.
        """
        cls._depth += 1
        try:
            yield
        finally:
            cls._depth -= 1

    @classmethod
    def is_in_not_context(cls) -> bool:
        """Check if we're in a NOT context with odd nesting depth."""
        return cls._depth % 2 == 1


def json_dump_field_as_sql(
    pb: ParamBuilder,
    table_alias: str,
    root_field_sanitized: str,
    extra_path: list[str] | None = None,
    cast: tsi_query.CastTo | None = None,
    use_agg_fn: bool = True,
    agg_fn: str | None = None,
) -> str:
    """Build SQL for JSON field access with optional type conversion.

    Args:
        pb: Parameter builder for SQL parameters
        table_alias: Table alias for the query
        root_field_sanitized: The root field name (already sanitized)
        extra_path: Optional list of JSON path components
        cast: Optional type to cast the result to
        use_agg_fn: Whether to use aggregate functions
        agg_fn: When set, `root_field_sanitized` is the raw (un-aggregated)
            column and the aggregate wraps the extracted scalar, not the dump:
            `{agg_fn}If(JSON_VALUE(col, path), col IS NOT NULL)`. This keeps
            GROUP BY state at one scalar per group instead of the whole JSON
            dump, avoiding the memory blow-up of `{agg_fn}(dump)`-then-extract.
            NULL-guarded so only rows carrying the dump contribute, matching
            the aggregate-then-extract result.

    Returns:
        str: SQL expression for accessing the JSON field

    Examples:
        >>> pb = ParamBuilder()
        >>> json_dump_field_as_sql(pb, "table", "any(inputs_dump)", ["model", "temperature"])
        'toFloat64(JSON_VALUE(any(inputs_dump), {param_1:String}))'
    """
    if cast != "exists":
        if cast is None and not use_agg_fn and not extra_path:
            return f"{root_field_sanitized}"

        path_str = "'$'"
        if extra_path:
            param_name = pb.add_param(quote_json_path_parts(extra_path))
            path_str = param_slot(param_name, "String")
        json_value = f"JSON_VALUE({root_field_sanitized}, {path_str})"
        if agg_fn:
            json_value = f"{agg_fn}If({json_value}, {root_field_sanitized} IS NOT NULL)"
        val = f"coalesce(nullIf({json_value}, 'null'), '')"
        return clickhouse_cast_json_value(val, cast)
    else:
        # Note: ClickHouse has limitations in distinguishing between null, non-existent, empty string, and "null".
        # This workaround helps to handle these cases.
        path_parts = []
        if extra_path:
            for part in extra_path:
                path_parts.append(", " + param_slot(pb.add_param(part), "String"))
        safe_path = "".join(path_parts)
        return f"(NOT (JSONType({root_field_sanitized}{safe_path}) = 'Null' OR JSONType({root_field_sanitized}{safe_path}) IS NULL))"
