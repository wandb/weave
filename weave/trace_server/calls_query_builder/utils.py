import contextlib
import datetime
import logging
from collections.abc import Generator

import sqlparse

from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import ParamBuilder, clickhouse_cast, quote_json_path_parts


def safe_alias(field_name: str) -> str:
    """Backtick-quote field names containing dots for use as SQL aliases."""
    return f"`{field_name}`" if "." in field_name else field_name


def param_slot(param_name: str, param_type: str) -> str:
    """Helper function to create a parameter slot for a clickhouse query."""
    return f"{{{param_name}:{param_type}}}"


def timestamp_to_datetime_str(timestamp: float) -> str:
    """Convert a unix timestamp to a ClickHouse-compatible datetime string.

    Args:
        timestamp (int | float): Unix timestamp in seconds.

    Returns:
        str: Datetime string in the format ``YYYY-MM-DD HH:MM:SS.ffffff``,
            matching the precision of ClickHouse ``DateTime64(6)`` columns.

    Examples:
        >>> timestamp_to_datetime_str(1709251200)
        '2024-03-01 00:00:00.000000'
    """
    return datetime.datetime.fromtimestamp(
        timestamp, tz=datetime.timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S.%f")


def parse_string_to_utc_timestamp(value: str) -> float | None:
    """Parse a string date or datetime into a UTC unix timestamp (seconds).

    Rules:

    * ``YYYY-MM-DD`` (exactly 10 characters after strip) is interpreted as
      midnight UTC on that calendar day.
    * ISO-8601 datetimes are parsed via :func:`datetime.datetime.fromisoformat`.
      ``Z`` / ``z`` suffix is accepted as UTC. Naive datetimes are treated as UTC
      wall time.
    * Unparsable strings return ``None`` (no conversion).

    Args:
        value: User-provided string literal.

    Returns:
        Unix timestamp in seconds in UTC, or ``None`` if not parseable.

    Examples:
        >>> parse_string_to_utc_timestamp("2024-03-01")
        1709251200.0
        >>> parse_string_to_utc_timestamp("2024-03-01T12:00:00Z") == parse_string_to_utc_timestamp(
        ...     "2024-03-01T12:00:00+00:00"
        ... )
        True
        >>> parse_string_to_utc_timestamp("not a date") is None
        True
    """
    s = value.strip()
    if not s:
        return None

    # Check for a date without a time
    # string: 'YYYY-MM-DD'
    # index:   0123456789
    # length: 10
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        try:
            d = datetime.date.fromisoformat(s)
        except ValueError:
            return None
        dt = datetime.datetime.combine(
            d, datetime.time.min, tzinfo=datetime.timezone.utc
        )
        return dt.timestamp()

    iso = s
    if iso.endswith(("Z", "z")):
        iso = iso[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(iso)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    else:
        dt = dt.astimezone(datetime.timezone.utc)
    return dt.timestamp()


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
