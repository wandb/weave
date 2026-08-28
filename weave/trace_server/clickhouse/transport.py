"""ClickHouse connection config, transports, and the call logic they share.

`ClickHouseConfig` is the connection. `SyncClickHouseTransport` and
`AsyncClickHouseTransport` are the two ways to run a call against it: the
blocking driver on a thread-local client, and clickhouse-connect's aiohttp
`AsyncClient` bound to one event loop.

Everything a call does apart from the driver invocation — settings merge,
correlation id, logging, error mapping, the insert retry decision — lives in the
`prepare_*` / `record_*` / `raise_*` functions below, which both transports'
callers share.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, NoReturn

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.query import QueryResult
from clickhouse_connect.driver.summary import QuerySummary

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server.clickhouse.utilities import (
    convert_to_insert_too_large,
    log_and_raise_insert_error,
    process_parameters,
    record_query_id,
    sanitize_invalid_utf8_surrogates,
    set_correlation_id,
)
from weave.trace_server.datadog import (
    record_db_insert,
    set_current_span_dd_tags,
    set_root_span_dd_tags,
)
from weave.trace_server.errors import handle_clickhouse_query_error
from weave.trace_server.ids import generate_id

logger = logging.getLogger(__name__)

CLICKHOUSE_DEFAULT_PORT = 8123
CLICKHOUSE_SECURE_PORT = 8443

# aiohttp connector caps for the native async client. `connector_limit_per_host`
# is the real concurrency ceiling: weave-trace talks to one host, so this is the
# async analogue of the thread pool's width.
ACH_CONNECTOR_LIMIT = 200
ACH_CONNECTOR_LIMIT_PER_HOST = 100


@dataclass(frozen=True)
class ClickHouseConfig:
    """Where and how to connect. Shared verbatim by both transports."""

    host: str
    port: int = CLICKHOUSE_DEFAULT_PORT
    user: str = "default"
    password: str = ""
    database: str = "default"

    @property
    def secure(self) -> bool:
        return self.port == CLICKHOUSE_SECURE_PORT


# --- Prepared calls ---------------------------------------------------------


@dataclass(frozen=True)
class PreparedQuery:
    query: str
    parameters: dict[str, Any]
    column_formats: dict[str, Any] | None
    settings: dict[str, Any]
    correlation_id: str
    started: float


@dataclass(frozen=True)
class PreparedCommand:
    command: str
    parameters: dict[str, Any] | None
    settings: dict[str, Any]
    correlation_id: str
    started: float


@dataclass(frozen=True)
class PreparedInsert:
    table: str
    data: Sequence[Sequence[Any]]
    column_names: list[str]
    settings: dict[str, Any]
    correlation_id: str
    started: float
    async_insert: bool


def _elapsed_ms(started: float) -> float:
    return round((time.monotonic() - started) * 1000, 1)


# --- Query ------------------------------------------------------------------


def prepare_query(
    query: str,
    parameters: dict[str, Any],
    column_formats: dict[str, Any] | None = None,
    settings: dict[str, int | str] | None = None,
) -> PreparedQuery:
    merged = ch_settings.merge_default_query_settings(settings)
    return PreparedQuery(
        query=query,
        parameters=process_parameters(parameters),
        column_formats=column_formats,
        settings=merged,
        correlation_id=set_correlation_id(merged),
        started=time.monotonic(),
    )


def record_query_success(prepared: PreparedQuery, result: QueryResult) -> None:
    logger.info(
        "clickhouse_query",
        extra={
            "trace_duration_ms": _elapsed_ms(prepared.started),
            "query": prepared.query,
            "parameters": prepared.parameters,
            "summary": result.summary,
            "query_id": record_query_id(result),
            "correlation_id": prepared.correlation_id,
        },
    )


def raise_query_error(prepared: PreparedQuery, error: Exception) -> NoReturn:
    logger.exception(
        "clickhouse_query_error",
        extra={
            "trace_duration_ms": _elapsed_ms(prepared.started),
            "error_str": str(error),
            "query": prepared.query,
            "parameters": prepared.parameters,
            "correlation_id": prepared.correlation_id,
        },
    )
    # always raises, optionally with custom error class
    handle_clickhouse_query_error(error)
    raise error


# --- Command ----------------------------------------------------------------


def prepare_command(
    command: str,
    parameters: dict[str, Any] | None = None,
    settings: dict[str, int | str] | None = None,
) -> PreparedCommand:
    merged = ch_settings.merge_default_command_settings(settings)
    return PreparedCommand(
        command=command,
        parameters=process_parameters(parameters) if parameters else None,
        settings=merged,
        correlation_id=set_correlation_id(merged),
        started=time.monotonic(),
    )


def record_command_success(prepared: PreparedCommand, result: Any) -> None:
    # command() also returns scalars, which carry no query_id.
    query_id = record_query_id(result) if isinstance(result, QuerySummary) else None
    logger.info(
        "clickhouse_command",
        extra={
            "trace_duration_ms": _elapsed_ms(prepared.started),
            "command": prepared.command,
            "parameters": prepared.parameters,
            "query_id": query_id,
            "correlation_id": prepared.correlation_id,
        },
    )


def raise_command_error(prepared: PreparedCommand, error: Exception) -> NoReturn:
    logger.exception(
        "clickhouse_command_error",
        extra={
            "trace_duration_ms": _elapsed_ms(prepared.started),
            "error_str": str(error),
            "command": prepared.command,
            "parameters": prepared.parameters,
            "correlation_id": prepared.correlation_id,
        },
    )
    handle_clickhouse_query_error(error)
    raise error


# --- Insert -----------------------------------------------------------------


def prepare_insert(
    table: str,
    data: Sequence[Sequence[Any]],
    column_names: list[str],
    settings: dict[str, Any] | None = None,
    do_sync_insert: bool = False,  # overrides use_async_insert
    *,
    use_async_insert: bool,
    use_replicated_tables: bool,
) -> PreparedInsert:
    record_db_insert(table=table, count=len(data))
    set_current_span_dd_tags({"clickhouse_trace_server_batched._insert.table": table})
    set_root_span_dd_tags(
        {
            "weave_trace_server.insert.table": table,
            "weave_trace_server.insert.row_count": len(data),
        }
    )

    async_insert = use_async_insert and not do_sync_insert
    if async_insert:
        settings = ch_settings.update_settings_for_async_insert(settings)
        set_current_span_dd_tags(
            {"clickhouse_trace_server_batched._insert.async_insert": True}
        )

    settings = dict(settings or {})
    # Replicated/distributed engines block-dedup byte-identical inserts;
    # a unique token opts out (non-replicated CH Cloud is unaffected).
    if use_replicated_tables:
        settings["insert_deduplication_token"] = generate_id()

    return PreparedInsert(
        table=table,
        data=data,
        column_names=column_names,
        settings=settings,
        # One correlation id covers both attempts: it is the same logical write.
        correlation_id=set_correlation_id(settings),
        started=time.monotonic(),
        async_insert=async_insert,
    )


def record_insert_success(prepared: PreparedInsert, result: QuerySummary) -> None:
    logger.info(
        "clickhouse_insert",
        extra={
            "trace_duration_ms": _elapsed_ms(prepared.started),
            "table": prepared.table,
            "row_count": len(prepared.data),
            "async_insert": prepared.async_insert,
            "query_id": record_query_id(result),
            "correlation_id": prepared.correlation_id,
        },
    )


def insert_retry_or_raise(
    prepared: PreparedInsert, error: Exception, sanitized: bool
) -> PreparedInsert:
    """The insert to retry, or log and raise. Retries at most once.

    Invalid client Unicode is the only retryable failure: sanitize the batch and
    send it again. `UnicodeEncodeError` subclasses `ValueError`, so it has to be
    tested before the InsertTooLarge conversion below it.
    """
    if isinstance(error, UnicodeEncodeError):
        if not sanitized:
            return replace(
                prepared, data=sanitize_invalid_utf8_surrogates(prepared.data)
            )
    elif isinstance(error, ValueError):
        error = convert_to_insert_too_large(error)
    log_and_raise_insert_error(
        error, prepared.table, prepared.data, prepared.correlation_id
    )
    raise error


# --- Transports -------------------------------------------------------------


class SyncClickHouseTransport:
    """The blocking driver, one client per thread over a shared pool manager.

    Per-thread because the driver refuses concurrent queries on one client.
    """

    def __init__(self, config: ClickHouseConfig, pool_mgr: Any) -> None:
        self._config = config
        self._pool_mgr = pool_mgr
        self._thread_local = threading.local()
        self._init_lock = threading.Lock()
        self._database_ensured = False

    @property
    def client(self) -> CHClient:
        if not hasattr(self._thread_local, "client"):
            self._thread_local.client = self.mint()
        return self._thread_local.client

    def mint(self, send_receive_timeout: int | None = None) -> CHClient:
        """Create a new client on the shared pool manager.

        autogenerate_session_id=False: weave-trace uses no session features,
        and the default collides on overlapping queries with SESSION_IS_LOCKED
        (code 373). See PR #6655.
        autogenerate_query_id=False: the default collides on a resent request
        with QUERY_WITH_SAME_ID_IS_ALREADY_RUNNING (code 216). See PR #7787.
        `send_receive_timeout` overrides the HTTP read timeout (migration clients
        need to outlast replicated-DDL propagation); None keeps the library default.
        """
        optional_kwargs: dict[str, int] = {}
        if send_receive_timeout is not None:
            optional_kwargs["send_receive_timeout"] = send_receive_timeout
        client = clickhouse_connect.get_client(
            host=self._config.host,
            port=self._config.port,
            user=self._config.user,
            password=self._config.password,
            secure=self._config.secure,
            pool_mgr=self._pool_mgr,
            autogenerate_session_id=False,
            autogenerate_query_id=False,
            **optional_kwargs,
        )
        self._ensure_database(client)
        client.database = self._config.database
        return client

    def _ensure_database(self, client: CHClient) -> None:
        """Run CREATE DATABASE IF NOT EXISTS once per process."""
        if self._database_ensured:
            return
        with self._init_lock:
            if self._database_ensured:
                return
            client.command(f"CREATE DATABASE IF NOT EXISTS {self._config.database}")
            self._database_ensured = True

    def query(self, prepared: PreparedQuery) -> QueryResult:
        return self.client.query(
            prepared.query,
            parameters=prepared.parameters,
            column_formats=prepared.column_formats,
            use_none=True,
            settings=prepared.settings,
        )

    def command(self, prepared: PreparedCommand) -> Any:
        return self.client.command(
            prepared.command,
            parameters=prepared.parameters,
            settings=prepared.settings,
        )

    def insert(self, prepared: PreparedInsert) -> QuerySummary:
        return self.client.insert(
            prepared.table,
            data=prepared.data,
            column_names=prepared.column_names,
            settings=prepared.settings,
        )


class AsyncClickHouseTransport:
    """clickhouse-connect's aiohttp `AsyncClient`.

    Start, use and close it on one event loop: an aiohttp session belongs to the
    loop that opened it. That is the caller's invariant to keep; one worker owns
    one loop and one transport.
    """

    def __init__(self, config: ClickHouseConfig) -> None:
        self._config = config
        self._client: AsyncClient | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> AsyncClient:
        """Open the session if it is not open yet, and return it.

        Locked because concurrent first calls would otherwise each connect.
        """
        if self._client is not None:
            return self._client
        async with self._lock:
            if self._client is None:
                self._client = await self._connect()
            return self._client

    async def _connect(self) -> AsyncClient:
        client = await clickhouse_connect.get_async_client(
            host=self._config.host,
            port=self._config.port,
            username=self._config.user,
            password=self._config.password,
            secure=self._config.secure,
            autogenerate_session_id=False,
            autogenerate_query_id=False,
            connector_limit=ACH_CONNECTOR_LIMIT,
            connector_limit_per_host=ACH_CONNECTOR_LIMIT_PER_HOST,
        )
        # The session exists before the database does. Anything that stops us
        # returning it -- a failed CREATE DATABASE, or cancellation -- has to
        # close it here, or `start()` retries and leaks another connector each
        # time. BaseException so CancelledError is covered too.
        try:
            await client.command(
                f"CREATE DATABASE IF NOT EXISTS {self._config.database}"
            )
        except BaseException:
            await client.close()
            raise
        client.database = self._config.database
        return client

    async def close(self) -> None:
        """Drain the aiohttp session. Workers call this on shutdown."""
        async with self._lock:
            if self._client is not None:
                await self._client.close()
                self._client = None

    async def query(self, prepared: PreparedQuery) -> QueryResult:
        client = await self.start()
        return await client.query(
            prepared.query,
            parameters=prepared.parameters,
            column_formats=prepared.column_formats,
            use_none=True,
            settings=prepared.settings,
        )

    async def command(self, prepared: PreparedCommand) -> Any:
        client = await self.start()
        return await client.command(
            prepared.command,
            parameters=prepared.parameters,
            settings=prepared.settings,
        )

    async def insert(self, prepared: PreparedInsert) -> QuerySummary:
        client = await self.start()
        return await client.insert(
            prepared.table,
            data=prepared.data,
            column_names=prepared.column_names,
            settings=prepared.settings,
        )
