import contextlib
import logging
from collections.abc import Generator
from typing import Optional

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
    extra_path: Optional[list[str]] = None,
    cast: Optional[tsi_query.CastTo] = None,
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

def split_escaped_field_path(path: str) -> list[str]:
    r"""Split a field path on dots, respecting backslash-escaped dots.

    This function handles field names that contain literal dots by allowing
    them to be escaped with a backslash. This is necessary because JSON keys
    can contain dots, and we need a way to distinguish between:
    - Nested field access: "output.metrics.run" -> ["output", "metrics", "run"]
    - Field with dot in name: "output.metrics\.run" -> ["output", "metrics.run"]

    Args:
        path: The field path string, potentially with escaped dots

    Returns:
        List of field path segments with escape sequences removed

    Examples:
        >>> split_escaped_field_path("output.metrics.run")
        ['output', 'metrics', 'run']
        >>> split_escaped_field_path("output.metrics\\.run")
        ['output', 'metrics.run']
        >>> split_escaped_field_path("output.a\\.b\\.c.d")
        ['output', 'a.b.c', 'd']
    """
    parts: list[str] = []
    current_part: list[str] = []
    i = 0

    while i < len(path):
        if path[i] == '\\' and i + 1 < len(path) and path[i + 1] == '.':
            # Escaped dot - add literal dot to current part
            current_part.append('.')
            i += 2
        elif path[i] == '.':
            # Unescaped dot - field separator
            if current_part or len(parts) == 0:  # Handle empty parts at start
                parts.append(''.join(current_part))
                current_part = []
            i += 1
        else:
            # Regular character
            current_part.append(path[i])
            i += 1

    # Add the last part
    if current_part or len(parts) > 0:
        parts.append(''.join(current_part))

    return parts
