import contextlib
import logging
from collections.abc import Generator

import sqlparse

from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import ParamBuilder, clickhouse_cast, quote_json_path_parts


def param_slot(param_name: str, param_type: str) -> str:
    """Helper function to create a parameter slot for a clickhouse query."""
    return f"{{{param_name}:{param_type}}}"


def safely_format_sql(
    sql: str,
    logger: logging.Logger,
) -> str:
    """Safely format a SQL string with parameters."""
    try:
        return sqlparse.format(sql, reindent=True)
    except:
        logger.info(f"Failed to format SQL: {sql}")
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
) -> str:
    """Build SQL for JSON field access with optional type conversion.

    Args:
        pb: Parameter builder for SQL parameters
        table_alias: Table alias for the query
        root_field_sanitized: The root field name (already sanitized)
        extra_path: Optional list of JSON path components
        cast: Optional type to cast the result to
        use_agg_fn: Whether to use aggregate functions

    Returns:
        str: SQL expression for accessing the JSON field

    Examples:
        >>> pb = ParamBuilder()
        >>> json_dump_field_as_sql(pb, "table", "any(inputs_dump)", ["model", "temperature"])
        'toFloat64(JSON_VALUE(any(inputs_dump), {param_1:String}))'
    """
    if cast != "exists":
        if not use_agg_fn and not extra_path:
            return f"{root_field_sanitized}"

        path_str = "'$'"
        if extra_path:
            param_name = pb.add_param(quote_json_path_parts(extra_path))
            path_str = param_slot(param_name, "String")
        val = f"coalesce(nullIf(JSON_VALUE({root_field_sanitized}, {path_str}), 'null'), '')"
        return clickhouse_cast(val, cast)
    else:
        # Note: ClickHouse has limitations in distinguishing between null, non-existent, empty string, and "null".
        # This workaround helps to handle these cases.
        path_parts = []
        if extra_path:
            for part in extra_path:
                path_parts.append(", " + param_slot(pb.add_param(part), "String"))
        safe_path = "".join(path_parts)
        return f"(NOT (JSONType({root_field_sanitized}{safe_path}) = 'Null' OR JSONType({root_field_sanitized}{safe_path}) IS NULL))"
