# ClickHouse Client - Connection management and low-level operations

import datetime
import json
import logging
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.exceptions import DatabaseError
from clickhouse_connect.driver.httputil import get_pool_manager
from clickhouse_connect.driver.query import QueryResult
from clickhouse_connect.driver.summary import QuerySummary

from weave.trace_server import environment as wf_env
from weave.trace_server.clickhouse_query_layer import migrator as wf_migrator
from weave.trace_server.clickhouse_query_layer import settings as ch_settings
from weave.trace_server.datadog import set_current_span_dd_tags
from weave.trace_server.errors import handle_clickhouse_query_error

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Create a shared connection pool manager for all ClickHouse connections
# maxsize: Maximum connections per pool (set higher than thread count to avoid blocking)
# num_pools: Number of distinct connection pools (for different hosts/configs)
_CH_POOL_MANAGER = get_pool_manager(maxsize=50, num_pools=2)


class ClickHouseClient:
    """Manages ClickHouse connections and provides low-level database operations.

    This class handles:
    - Thread-local client management
    - Connection pooling
    - Query execution (_query, _query_stream)
    - Command execution (_command)
    - Data insertion (_insert)
    - Database migrations
    """

    def __init__(
        self,
        *,
        host: str,
        port: int = 8123,
        user: str = "default",
        password: str = "",
        database: str = "default",
        use_async_insert: bool = False,
    ):
        self._thread_local = threading.local()
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._use_async_insert = use_async_insert

    @classmethod
    def from_env(cls, use_async_insert: bool = False) -> "ClickHouseClient":
        """Create a ClickHouseClient from environment variables."""
        return ClickHouseClient(
            host=wf_env.wf_clickhouse_host(),
            port=wf_env.wf_clickhouse_port(),
            user=wf_env.wf_clickhouse_user(),
            password=wf_env.wf_clickhouse_pass(),
            database=wf_env.wf_clickhouse_database(),
            use_async_insert=use_async_insert,
        )

    @property
    def ch_client(self) -> CHClient:
        """Returns a thread-local clickhouse client.

        Each thread gets its own client instance to avoid session conflicts,
        but all clients share the same underlying connection pool via _CH_POOL_MANAGER.
        """
        if not hasattr(self._thread_local, "ch_client"):
            self._thread_local.ch_client = self._mint_client()
        return self._thread_local.ch_client

    def _mint_client(self) -> CHClient:
        """Create a new ClickHouse client using the shared pool manager."""
        client = clickhouse_connect.get_client(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            secure=self._port == 8443,
            pool_mgr=_CH_POOL_MANAGER,
        )
        # Safely create the database if it does not exist
        client.command(f"CREATE DATABASE IF NOT EXISTS {self._database}")
        client.database = self._database
        return client

    @contextmanager
    def with_new_client(self) -> Iterator[None]:
        """Context manager to use a new client for operations.

        Each call gets a fresh client with its own clickhouse session ID.

        Usage:
        ```
        with self.with_new_client():
            self.feedback_query(req)
        ```
        """
        client = self._mint_client()
        original_client = self.ch_client
        self._thread_local.ch_client = client
        try:
            yield
        finally:
            self._thread_local.ch_client = original_client
            client.close()

    @property
    def use_distributed_mode(self) -> bool:
        """Check if ClickHouse is configured to use distributed tables.

        Returns:
            bool: True if using distributed tables, False otherwise.
        """
        return wf_env.wf_clickhouse_use_distributed_tables()

    @property
    def clickhouse_cluster_name(self) -> str | None:
        """Get the ClickHouse cluster name from environment.

        Returns:
            str | None: The cluster name, or None if not set.
        """
        return wf_env.wf_clickhouse_replicated_cluster()

    def run_migrations(self) -> None:
        """Run database migrations."""
        logger.info("Running migrations")
        migrator = wf_migrator.get_clickhouse_trace_server_migrator(
            self._mint_client(),
            replicated=wf_env.wf_clickhouse_replicated(),
            replicated_path=wf_env.wf_clickhouse_replicated_path(),
            replicated_cluster=wf_env.wf_clickhouse_replicated_cluster(),
            use_distributed=wf_env.wf_clickhouse_use_distributed_tables(),
        )
        migrator.apply_migrations(self._database)

    def query_stream(
        self,
        query: str,
        parameters: dict[str, Any],
        column_formats: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> Iterator[tuple]:
        """Stream the results of a query from the database."""
        if not settings:
            settings = {}
        settings.update(ch_settings.CLICKHOUSE_DEFAULT_QUERY_SETTINGS)

        summary = None
        parameters = _process_parameters(parameters)
        try:
            with self.ch_client.query_rows_stream(
                query,
                parameters=parameters,
                column_formats=column_formats,
                use_none=True,
                settings=settings,
            ) as stream:
                if isinstance(stream.source, QueryResult):
                    summary = stream.source.summary
                logger.info(
                    "clickhouse_stream_query",
                    extra={
                        "query": query,
                        "parameters": parameters,
                        "summary": summary,
                    },
                )
                yield from stream
        except Exception as e:
            logger.exception(
                "clickhouse_stream_query_error",
                extra={
                    "error_str": str(e),
                    "query": query,
                    "parameters": parameters,
                },
            )
            # always raises, optionally with custom error class
            handle_clickhouse_query_error(e)

    def query(
        self,
        query: str,
        parameters: dict[str, Any],
        column_formats: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Directly query the database and return the result."""
        if not settings:
            settings = {}
        settings.update(ch_settings.CLICKHOUSE_DEFAULT_QUERY_SETTINGS)

        parameters = _process_parameters(parameters)
        try:
            res = self.ch_client.query(
                query,
                parameters=parameters,
                column_formats=column_formats,
                use_none=True,
                settings=settings,
            )
        except Exception as e:
            logger.exception(
                "clickhouse_query_error",
                extra={"error_str": str(e), "query": query, "parameters": parameters},
            )
            # always raises, optionally with custom error class
            handle_clickhouse_query_error(e)
            return None  # type: ignore

        logger.info(
            "clickhouse_query",
            extra={
                "query": query,
                "parameters": parameters,
                "summary": res.summary,
            },
        )
        return res

    def command(
        self,
        command: str,
        parameters: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        """Execute a mutation command (INSERT, UPDATE, DELETE) that doesn't return results.

        Args:
            command: The SQL command to execute.
            parameters: Optional dictionary of query parameters.
            settings: Optional dictionary of ClickHouse settings.
        """
        if not settings:
            settings = {}
        settings.update(ch_settings.CLICKHOUSE_DEFAULT_QUERY_SETTINGS)

        processed_params = _process_parameters(parameters) if parameters else None
        try:
            self.ch_client.command(
                command,
                parameters=processed_params,
                settings=settings,
            )
        except Exception as e:
            logger.exception(
                "clickhouse_command_error",
                extra={
                    "error_str": str(e),
                    "command": command,
                    "parameters": processed_params,
                },
            )
            handle_clickhouse_query_error(e)
            return

        logger.info(
            "clickhouse_command",
            extra={
                "command": command,
                "parameters": processed_params,
            },
        )
        return

    def insert(
        self,
        table: str,
        data: Sequence[Sequence[Any]],
        column_names: list[str],
        settings: dict[str, Any] | None = None,
        do_sync_insert: bool = False,
    ) -> QuerySummary:
        """Insert data into a table.

        Args:
            table: The table name to insert into.
            data: The data rows to insert.
            column_names: The column names for the data.
            settings: Optional ClickHouse settings.
            do_sync_insert: If True, use synchronous insert (overrides _use_async_insert).

        Returns:
            QuerySummary: Summary of the insert operation.
        """
        set_current_span_dd_tags(
            {
                "clickhouse_client.insert.table": table,
            }
        )

        if self._use_async_insert and not do_sync_insert:
            settings = ch_settings.update_settings_for_async_insert(settings)
            set_current_span_dd_tags(
                {
                    "clickhouse_client.insert.async_insert": True,
                }
            )

        for attempt in range(ch_settings.INSERT_MAX_RETRIES):
            try:
                return self.ch_client.insert(
                    table, data=data, column_names=column_names, settings=settings
                )

            # InsertTooLarge: raise immediately, no retry
            except ValueError as e:
                converted = _convert_to_insert_too_large(e)
                _log_and_raise_insert_error(converted, table, data)

            # Empty query error: RETRY (generator was consumed during HTTP retry)
            except DatabaseError as e:
                if _should_retry_empty_query(e, table, attempt):
                    continue
                _log_and_raise_insert_error(e, table, data)

            # All other errors: raise immediately, no retry
            except Exception as e:
                _log_and_raise_insert_error(e, table, data)

        # Should never reach here, but satisfy type checker
        raise RuntimeError("Insert failed after all retries")


# =============================================================================
# Utility Functions
# =============================================================================


def _process_parameters(parameters: dict[str, Any] | None) -> dict[str, Any]:
    """Process query parameters, converting datetimes to timestamps.

    Special processing for datetimes! For some reason, the clickhouse connect
    client truncates the datetime to the nearest second, so we need to convert
    the datetime to a float which is then converted back to a datetime in the
    clickhouse query.
    """
    if parameters is None:
        return {}
    parameters = parameters.copy()
    for key, value in parameters.items():
        if isinstance(value, datetime.datetime):
            parameters[key] = value.timestamp()
    return parameters


def ensure_datetimes_have_tz(
    dt: datetime.datetime | None = None,
) -> datetime.datetime | None:
    """Ensure datetime has timezone info, defaulting to UTC.

    Clickhouse does not support timezone-aware datetimes. You can specify the
    desired timezone at query time. However, clickhouse will produce a
    timezone-naive datetime when the preferred timezone is UTC. This function
    ensures that the datetime has a timezone, and if it does not, it adds the
    UTC timezone to correctly convey that the datetime is in UTC for the caller.

    See: https://github.com/ClickHouse/clickhouse-connect/issues/210
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def ensure_datetimes_have_tz_strict(dt: datetime.datetime) -> datetime.datetime:
    """Ensure datetime has timezone info, raising if None."""
    res = ensure_datetimes_have_tz(dt)
    if res is None:
        raise ValueError(f"Datetime is None: {dt}")
    return res


def datetime_to_microseconds(dt: datetime.datetime) -> int:
    """Convert a datetime to microseconds since Unix epoch.

    This is needed for DateTime64(6) parameterized queries because
    clickhouse-connect truncates datetime objects to whole seconds
    when passing them as parameters. By converting to microseconds
    and using Int64 type, we preserve full precision.

    Args:
        dt: A datetime object (should be timezone-aware).

    Returns:
        int: Microseconds since Unix epoch (1970-01-01 00:00:00 UTC).

    Examples:
        >>> import datetime
        >>> dt = datetime.datetime(2026, 1, 14, 23, 15, 38, 704246, tzinfo=datetime.timezone.utc)
        >>> datetime_to_microseconds(dt)
        1768432538704246
    """
    # Ensure we have timezone info for accurate conversion
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    # Convert to microseconds: timestamp() gives seconds as float, multiply by 1M
    return int(dt.timestamp() * 1_000_000)


def dict_value_to_dump(value: dict) -> str:
    """Convert a dict to JSON string."""
    if not isinstance(value, dict):
        raise TypeError(f"Value is not a dict: {value}")
    return json.dumps(value)


def any_value_to_dump(value: Any) -> str:
    """Convert any value to JSON string."""
    return json.dumps(value)


def dict_dump_to_dict(val: str) -> dict[str, Any]:
    """Convert JSON string to dict."""
    res = json.loads(val)
    if not isinstance(res, dict):
        raise TypeError(f"Value is not a dict: {val}")
    return res


def any_dump_to_any(val: str) -> Any:
    """Convert JSON string to any value."""
    return json.loads(val)


def nullable_any_dump_to_any(val: str | None) -> Any | None:
    """Convert nullable JSON string to any value."""
    return any_dump_to_any(val) if val else None


def empty_str_to_none(val: str | None) -> str | None:
    """Convert empty string to None."""
    if val == "":
        return None
    return val


def num_bytes(data: Any) -> int:
    """Calculate the number of bytes in a string.

    This can be computationally expensive, only call when necessary.
    Never raise on a failed str cast, just return 0.
    """
    try:
        return len(str(data).encode("utf-8"))
    except Exception:
        return 0


# =============================================================================
# Insert Error Helpers
# =============================================================================


def _convert_to_insert_too_large(e: Exception) -> Exception:
    """Convert ValueError to InsertTooLarge if the error indicates data is too large."""
    from weave.trace_server.errors import InsertTooLarge

    if isinstance(e, ValueError) and "negative shift count" in str(e):
        return InsertTooLarge(
            "Database insertion failed. Record too large. "
            "A likely cause is that a single row or cell exceeded "
            "the limit. If logging images, save them as `Image.PIL`."
        )
    return e


def _should_retry_empty_query(e: Exception, table: str, attempt: int) -> bool:
    """Check if we should retry an empty query error.

    Attempts to fix a longstanding "Empty query" error that intermittently
    occurs during ClickHouse inserts. This happens when clickhouse-connect's
    internal serialization generator gets exhausted during an HTTP connection
    retry (after CH Cloud's keep-alive timeout causes a connection reset).
    """
    is_empty_query = isinstance(e, DatabaseError) and "Empty query" in str(e)
    should_retry = is_empty_query and attempt < ch_settings.INSERT_MAX_RETRIES - 1
    if should_retry:
        logger.warning(
            "clickhouse_insert_empty_query_retry",
            extra={
                "table": table,
                "attempt": attempt + 1,
                "max_retries": ch_settings.INSERT_MAX_RETRIES,
            },
        )
    return should_retry


def _log_and_raise_insert_error(
    e: Exception, table: str, data: Sequence[Sequence[Any]]
) -> None:
    """Log insert error with data size info and re-raise."""
    data_bytes = sum(num_bytes(row) for row in data)
    logger.exception(
        "clickhouse_insert_error",
        extra={
            "error_str": str(e),
            "table": table,
            "data_len": len(data),
            "data_bytes": data_bytes,
        },
    )
    raise e
