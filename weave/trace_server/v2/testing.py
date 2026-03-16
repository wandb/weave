"""V2 test fixtures.

Drop-in replacements for the existing test wiring. The existing chain:

    SqliteTraceServer → ExternalTraceServer → CachingMiddleware → WeaveClient

becomes:

    SqliteStorage → TraceService → DirectClient → WeaveClient

Same fixture interface (`trace_server` returns something WeaveClient can use),
but cleanly layered with no hasattr hacks.
"""

from __future__ import annotations

from weave.trace_server.external_to_internal_trace_server_adapter import (
    IdConverter,
)
from weave.trace_server.v2.service import TraceService
from weave.trace_server.v2.storage_clickhouse import ClickHouseStorage
from weave.trace_server.v2.storage_interface import StorageInterface
from weave.trace_server.v2.storage_sqlite import SqliteStorage
from weave.trace_server_bindings.v2.client_direct import DirectClient
from weave.trace_server_bindings.v2.client_interface import ClientInterface


def create_sqlite_client(
    db_path: str = "file::memory:?cache=shared",
    id_converter: IdConverter | None = None,
) -> ClientInterface:
    """Create a V2 test client backed by SQLite.

    Equivalent to the old:
        sqlite_server = SqliteTraceServer(db_path)
        external = ExternalTraceServer(sqlite_server, id_converter)
        caching = CachingMiddlewareTraceServer.from_env(external)
        client = WeaveClient(..., caching)

    Now:
        storage = SqliteStorage(db_path)
        service = TraceService(storage, id_converter)
        client = DirectClient(service)
    """
    storage = SqliteStorage(db_path)
    service = TraceService(storage, id_converter)
    return DirectClient(service)


def create_clickhouse_client(
    host: str,
    port: int = 8123,
    user: str = "default",
    password: str = "",
    database: str = "default",
    id_converter: IdConverter | None = None,
) -> ClientInterface:
    """Create a V2 test client backed by ClickHouse.

    Equivalent to the old:
        ch_server = ClickHouseTraceServer(host=host, port=port, ...)
        external = ExternalTraceServer(ch_server, id_converter)
        caching = CachingMiddlewareTraceServer.from_env(external)
        client = WeaveClient(..., caching)

    Now:
        storage = ClickHouseStorage(host=host, port=port, ...)
        service = TraceService(storage, id_converter)
        client = DirectClient(service)
    """
    storage = ClickHouseStorage(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )
    service = TraceService(storage, id_converter)
    return DirectClient(service)


def create_client_from_storage(
    storage: StorageInterface,
    id_converter: IdConverter | None = None,
) -> ClientInterface:
    """Create a V2 test client from any StorageInterface.

    Useful for custom test storage implementations.
    """
    service = TraceService(storage, id_converter)
    return DirectClient(service)
