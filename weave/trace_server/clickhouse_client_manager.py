"""ClickHouse client lifecycle management.

Encapsulates thread-local client creation, connection pooling, and database
initialization. Extracted from clickhouse_trace_server_batched.py to isolate
the ClickHouse connection layer — making it straightforward to swap in an
async client when clickhouse-connect's native async support stabilises.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import clickhouse_connect
from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.httputil import get_pool_manager

logger = logging.getLogger(__name__)

# Shared connection pool manager for all ClickHouse connections.
# maxsize: Maximum connections per pool (set higher than thread count to avoid blocking)
# num_pools: Number of distinct connection pools (for different hosts/configs)
_CH_POOL_MANAGER = get_pool_manager(maxsize=50, num_pools=2)


class ClickHouseClientManager:
    """Manages thread-local ClickHouse client instances with a shared connection pool.

    Each thread gets its own ``CHClient`` instance to avoid session conflicts,
    but all clients share the same underlying ``urllib3`` pool via
    ``_CH_POOL_MANAGER``.

    When clickhouse-connect ships a stable async client, an
    ``AsyncClickHouseClientManager`` can implement the same interface using
    ``clickhouse_connect.get_async_client()`` with ``aiohttp``'s native
    connection pooling — no thread-local storage needed.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int = 8123,
        user: str = "default",
        password: str = "",
        database: str = "default",
    ) -> None:
        self._thread_local = threading.local()
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._init_lock = threading.Lock()
        self._database_ensured = False

    @property
    def database(self) -> str:
        """The database name this manager targets."""
        return self._database

    @property
    def client(self) -> CHClient:
        """Return a thread-local ClickHouse client, creating one if needed."""
        if not hasattr(self._thread_local, "ch_client"):
            self._thread_local.ch_client = self.create_client()
        return self._thread_local.ch_client

    @contextmanager
    def new_client(self) -> Iterator[None]:
        """Context manager that temporarily swaps in a fresh client.

        Each call gets a fresh client with its own ClickHouse session ID.
        The previous client is restored on exit.
        """
        client = self.create_client()
        original_client = self.client
        self._thread_local.ch_client = client
        try:
            yield
        finally:
            self._thread_local.ch_client = original_client
            client.close()

    def _ensure_database(self, client: CHClient) -> None:
        """Run ``CREATE DATABASE IF NOT EXISTS`` once per process."""
        if self._database_ensured:
            return
        with self._init_lock:
            if self._database_ensured:
                return
            client.command(f"CREATE DATABASE IF NOT EXISTS {self._database}")
            self._database_ensured = True

    def create_client(self) -> CHClient:
        """Create a new ClickHouse client using the shared pool manager.

        The returned client is independent of the thread-local client and
        must be closed by the caller when no longer needed.
        """
        client = clickhouse_connect.get_client(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            secure=self._port == 8443,
            pool_mgr=_CH_POOL_MANAGER,
        )
        self._ensure_database(client)
        client.database = self._database
        return client
