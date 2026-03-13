"""Adapter that makes chDB's embedded ClickHouse engine look like a clickhouse_connect client.

This allows the ClickHouseTraceServer to run queries against an embedded
ClickHouse engine (via chDB) without requiring a separate ClickHouse server process.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import chdb

logger = logging.getLogger(__name__)


@dataclass
class ChdbQueryResult:
    """Duck-type compatible with clickhouse_connect.driver.query.QueryResult."""

    result_rows: list[tuple]
    column_names: list[str]
    summary: dict[str, Any] = field(default_factory=dict)

    @property
    def result_set(self) -> list[tuple]:
        return self.result_rows

    @property
    def row_count(self) -> int:
        return len(self.result_rows)


@dataclass
class ChdbQuerySummary:
    """Duck-type compatible with clickhouse_connect.driver.summary.QuerySummary."""

    written_rows: int = 0
    written_bytes: int = 0


class _RowStream:
    """Mimics the clickhouse_connect query_rows_stream context manager result."""

    def __init__(self, result: ChdbQueryResult) -> None:
        self.source = result
        self._rows = iter(result.result_rows)

    def __iter__(self) -> Iterator[tuple]:
        return self._rows

    def __next__(self) -> tuple:
        return next(self._rows)


# Regex to match {param_name:Type} placeholders used by clickhouse_connect
_PARAM_PATTERN = re.compile(r"\{(\w+):([^}]+)\}")


def _quote_table_name(table: str) -> str:
    """Quote a table name, handling database-qualified names like 'db.table'."""
    parts = table.split(".")
    return ".".join(f"`{p}`" for p in parts)


# Patterns for SQL features not supported by chDB's embedded engine
_SYNC_DROP_RE = re.compile(r"\bSYNC\s*$", re.IGNORECASE | re.MULTILINE)

# Settings not supported by chDB
# Note: enable_block_number_column and enable_block_offset_column ARE supported
_UNSUPPORTED_SETTINGS: list[str] = []


def _sanitize_sql_for_chdb(sql: str) -> str:
    """Remove or rewrite SQL features not supported by chDB.

    chDB is an embedded ClickHouse engine that doesn't support certain
    server-level features like SYNC drops or some table settings.
    """
    # DROP ... SYNC is not supported — just DROP
    sql = _SYNC_DROP_RE.sub("", sql)

    # Rewrite SETTINGS blocks to remove unsupported entries
    sql = _strip_unsupported_settings(sql)

    return sql


def _strip_unsupported_settings(sql: str) -> str:
    """Remove unsupported settings from SETTINGS clauses.

    Handles the full lifecycle:
    1. Remove individual unsupported setting entries
    2. Fix comma placement after removal
    3. Remove empty SETTINGS clause if all entries were removed
    """
    # Match SETTINGS keyword only when it appears as a SQL clause —
    # at the start of a line (with optional whitespace), not inside comments.
    # Captures everything until end of string (SETTINGS is always last in DDL).
    settings_pattern = re.compile(
        r"^([ \t]*)(SETTINGS)\n(.*)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )

    def process_settings_block(match: re.Match) -> str:
        indent = match.group(1)
        keyword = match.group(2)  # "SETTINGS"
        body = match.group(3)  # the settings entries

        # Parse individual settings (key = value pairs separated by commas)
        entries = re.split(r",", body)
        kept = []
        for entry in entries:
            entry_stripped = entry.strip()
            if not entry_stripped:
                continue
            # Check if this setting is unsupported
            is_unsupported = any(
                re.match(rf"{s}\s*=", entry_stripped, re.IGNORECASE)
                for s in _UNSUPPORTED_SETTINGS
            )
            if not is_unsupported:
                kept.append(entry_stripped)

        if not kept:
            return ""  # Remove entire SETTINGS clause
        return f"{indent}{keyword}\n    " + ",\n    ".join(kept)

    return settings_pattern.sub(process_settings_block, sql)


def _parse_datetime(val: str) -> datetime.datetime:
    """Parse a ClickHouse datetime string to a Python datetime."""
    # chDB JSON output formats: "2024-01-15 10:30:00" or "2024-01-15 10:30:00.123"
    val = val.strip()
    try:
        if "." in val:
            return datetime.datetime.strptime(val, "%Y-%m-%d %H:%M:%S.%f")
        return datetime.datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        # Fall back to returning the string if parsing fails
        return val  # type: ignore[return-value]


def _escape_string(value: str) -> str:
    """Escape a string value for ClickHouse SQL."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _format_value(value: Any, ch_type: str | None = None) -> str:
    """Format a Python value as a ClickHouse SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, datetime.datetime):
        # Strip timezone info — chDB doesn't support timezone offsets in literals
        naive = value.replace(tzinfo=None)
        # Only include microseconds if non-zero, since DateTime (non-64)
        # columns can't parse fractional seconds
        if naive.microsecond:
            return f"'{naive.strftime('%Y-%m-%d %H:%M:%S.%f')}'"
        return f"'{naive.strftime('%Y-%m-%d %H:%M:%S')}'"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # For DateTime64 parameters, the ClickHouse server expects timestamps
        # that were converted from datetime objects to floats by _process_parameters.
        # We need to convert them back if the type hint says DateTime64.
        if ch_type and "DateTime64" in ch_type:
            return f"toDateTime64({value}, 3)"
        return repr(value)
    if isinstance(value, str):
        return f"'{_escape_string(value)}'"
    if isinstance(value, (list, tuple)):
        # Array literal
        formatted = ", ".join(_format_value(v, None) for v in value)
        return f"[{formatted}]"
    if isinstance(value, dict):
        return f"'{_escape_string(json.dumps(value))}'"
    if isinstance(value, bytes):
        return f"unhex('{value.hex()}')"
    return f"'{_escape_string(str(value))}'"


def _inline_parameters(sql: str, parameters: dict[str, Any] | None) -> str:
    """Replace {param_name:Type} placeholders with literal values.

    clickhouse_connect uses this syntax for parameterized queries.
    chDB's session API takes raw SQL, so we inline the values.
    """
    if not parameters:
        return sql

    def replacer(match: re.Match) -> str:
        param_name = match.group(1)
        ch_type = match.group(2)
        if param_name not in parameters:
            # Leave the placeholder as-is if not in parameters
            return match.group(0)
        value = parameters[param_name]
        return _format_value(value, ch_type)

    return _PARAM_PATTERN.sub(replacer, sql)


def _parse_json_result(raw: bytes) -> ChdbQueryResult:
    """Parse a JSON-formatted chDB result into a ChdbQueryResult."""
    if not raw:
        return ChdbQueryResult(result_rows=[], column_names=[])

    text = raw.decode("utf-8").strip()
    if not text:
        return ChdbQueryResult(result_rows=[], column_names=[])

    data = json.loads(text)

    meta = data.get("meta", [])
    column_names = [col["name"] for col in meta]
    column_types = {col["name"]: col["type"] for col in meta}

    rows_data = data.get("data", [])
    result_rows = []
    for row_dict in rows_data:
        row = []
        for col_name in column_names:
            val = row_dict.get(col_name)
            val = _coerce_value(val, column_types.get(col_name, ""))
            row.append(val)
        result_rows.append(tuple(row))

    return ChdbQueryResult(result_rows=result_rows, column_names=column_names)


def _coerce_value(val: Any, ch_type: str) -> Any:
    """Coerce a JSON-deserialized value to the appropriate Python type.

    chDB's JSON output serializes some types as strings that we need to convert.
    clickhouse_connect returns datetime objects for DateTime columns, so we do too.
    """
    if val is None:
        return None

    # Strip Nullable wrapper
    inner_type = ch_type
    if inner_type.startswith("Nullable(") and inner_type.endswith(")"):
        inner_type = inner_type[9:-1]

    # DateTime64 types — parse string back to datetime
    if inner_type.startswith("DateTime64"):
        if isinstance(val, str):
            return _parse_datetime(val)
        return val

    # DateTime types (non-64)
    if inner_type.startswith("DateTime"):
        if isinstance(val, str):
            return _parse_datetime(val)
        return val

    # UInt / Int types
    if inner_type.startswith(("UInt", "Int")):
        try:
            return int(val)
        except (ValueError, TypeError):
            return val

    # Float types
    if inner_type.startswith("Float"):
        try:
            return float(val)
        except (ValueError, TypeError):
            return val

    # Bool
    if inner_type == "Bool":
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            return val.lower() in ("1", "true")
        return bool(val)

    return val


class ChdbClientAdapter:
    """Adapter that makes a chDB session look like a clickhouse_connect CHClient.

    This implements the subset of the CHClient interface used by
    ClickHouseTraceServer: query(), command(), insert(), query_rows_stream(),
    and the database property.
    """

    def __init__(self, path: str | None = None) -> None:
        """Create a new chDB client adapter.

        Args:
            path: Directory for persistent storage, or None for in-memory.
        """
        self._session = chdb.session.Session(path)
        self._database = "default"

    @property
    def database(self) -> str:
        return self._database

    @database.setter
    def database(self, db_name: str) -> None:
        self._database = db_name
        self._session.query(f"USE `{db_name}`")

    def query(
        self,
        sql: str,
        parameters: dict[str, Any] | None = None,
        column_formats: dict[str, Any] | None = None,
        use_none: bool = True,
        settings: dict[str, Any] | None = None,
    ) -> ChdbQueryResult:
        """Execute a query and return results."""
        formatted_sql = _inline_parameters(sql, parameters)
        self._apply_settings(settings)
        try:
            result = self._session.query(formatted_sql, "JSON")
            raw = result.bytes() if result else b""
        except Exception:
            logger.exception(
                "chdb_query_error",
                extra={"query": formatted_sql},
            )
            raise
        return _parse_json_result(raw)

    @contextmanager
    def query_rows_stream(
        self,
        sql: str,
        parameters: dict[str, Any] | None = None,
        column_formats: dict[str, Any] | None = None,
        use_none: bool = True,
        settings: dict[str, Any] | None = None,
    ) -> Iterator[_RowStream]:
        """Execute a query and yield a row stream.

        chDB doesn't have true streaming, so we execute the full query
        and wrap the result in a stream-like interface.
        """
        result = self.query(sql, parameters, column_formats, use_none, settings)
        yield _RowStream(result)

    def command(
        self,
        sql: str,
        parameters: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> str:
        """Execute a DDL/DML command that doesn't return a result set."""
        formatted_sql = _inline_parameters(sql, parameters)
        formatted_sql = _sanitize_sql_for_chdb(formatted_sql)
        self._apply_settings(settings)
        try:
            result = self._session.query(formatted_sql)
            return result.bytes().decode("utf-8") if result else ""
        except Exception:
            logger.exception(
                "chdb_command_error",
                extra={"command": formatted_sql},
            )
            raise

    def insert(
        self,
        table: str,
        data: Any,
        column_names: list[str] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> ChdbQuerySummary:
        """Insert data into a table.

        Converts columnar data to INSERT VALUES SQL since chDB doesn't have
        a native bulk insert API like clickhouse_connect.
        """
        if not data:
            return ChdbQuerySummary()

        if column_names is None:
            raise ValueError("column_names is required for chDB insert")

        cols = ", ".join(f"`{c}`" for c in column_names)

        # Build all value tuples
        value_rows = []
        for row in data:
            vals = []
            for val in row:
                vals.append(_format_value(val))
            value_rows.append(f"({', '.join(vals)})")

        # Batch inserts to avoid overly long SQL statements
        batch_size = 500
        total_written = 0
        for i in range(0, len(value_rows), batch_size):
            batch = value_rows[i : i + batch_size]
            values_sql = ", ".join(batch)
            sql = f"INSERT INTO {_quote_table_name(table)} ({cols}) VALUES {values_sql}"
            self._apply_settings(settings)
            self._session.query(sql)
            total_written += len(batch)

        return ChdbQuerySummary(written_rows=total_written)

    def close(self) -> None:
        """Close the session. No-op for chDB."""
        pass

    def _apply_settings(self, settings: dict[str, Any] | None) -> None:
        """Apply ClickHouse settings to the session.

        Some settings from the production ClickHouse server may not be
        supported by chDB. We silently skip unsupported ones.
        """
        if not settings:
            return
        # Known settings that chDB supports
        _SUPPORTED_SETTINGS = {
            "max_memory_usage",
            "max_execution_time",
            "function_json_value_return_type_allow_complex",
        }
        for key, value in settings.items():
            if key in _SUPPORTED_SETTINGS:
                try:
                    self._session.query(f"SET {key} = {value}")
                except Exception:
                    # Silently skip unsupported settings
                    pass
