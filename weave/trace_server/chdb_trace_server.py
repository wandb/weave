"""chDB-backed Trace Server.

Subclasses ClickHouseTraceServer but uses an embedded ClickHouse engine (chDB)
instead of a remote ClickHouse server. This gives ClickHouse SQL compatibility
without requiring a separate server process or Docker container.

Usage:
    server = ChdbTraceServer(db_path="/tmp/weave_chdb")
    server._run_migrations()
    # Now use like any other trace server
"""

from __future__ import annotations

import logging
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from cachetools import TTLCache

from weave.trace_server import clickhouse_trace_server_migrator as wf_migrator
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.chdb_client_adapter import (
    ChdbClientAdapter,
    ChdbQueryResult,
    ChdbQuerySummary,
)
from weave.trace_server.clickhouse_trace_server_batched import (
    ClickHouseTraceServer,
    _process_parameters,
    read_model_to_provider_info_map,
)

logger = logging.getLogger(__name__)

# chDB's embedded server can only be initialized with one path per process.
# We use a module-level singleton path to ensure all ChdbTraceServer instances
# share the same underlying storage.
_CHDB_SINGLETON_PATH: str | None = None
_CHDB_SINGLETON_LOCK = threading.Lock()


def _get_chdb_path(requested_path: str | None) -> str:
    """Get the chDB storage path, enforcing the singleton constraint.

    If no path has been set yet, creates a temp directory (if requested_path is None)
    or uses the provided path. If a path was already set, returns that same path
    (chDB requires all sessions in a process to use the same path).
    """
    global _CHDB_SINGLETON_PATH
    with _CHDB_SINGLETON_LOCK:
        if _CHDB_SINGLETON_PATH is not None:
            return _CHDB_SINGLETON_PATH

        if requested_path is None:
            _CHDB_SINGLETON_PATH = tempfile.mkdtemp(prefix="weave_chdb_")
        else:
            _CHDB_SINGLETON_PATH = requested_path
        return _CHDB_SINGLETON_PATH


class ChdbTraceServer(ClickHouseTraceServer):
    """Trace server backed by chDB (embedded ClickHouse).

    Inherits all business logic from ClickHouseTraceServer but overrides
    the connection layer to use chDB's in-process engine instead of
    a remote ClickHouse server via clickhouse_connect.
    """

    def __init__(
        self,
        *,
        db_path: str | None = None,
        database: str = "default",
        evaluate_model_dispatcher: Any | None = None,
    ):
        """Initialize the chDB trace server.

        Args:
            db_path: Directory for persistent chDB storage, or None for in-memory.
            database: ClickHouse database name to use.
            evaluate_model_dispatcher: Optional dispatcher for model evaluation.
        """
        # Do NOT call super().__init__() - it expects host/port for remote CH.
        # Instead, initialize all the fields that the parent class needs.
        self._db_path = db_path
        self._database = database
        self._thread_local = threading.local()
        self._use_async_insert = False  # No async in embedded mode
        self._model_to_provider_info_map = read_model_to_provider_info_map()
        self._init_lock = threading.Lock()
        self._file_storage_client = None
        self._file_storage_client_initialized = False
        self._kafka_producer = None
        self._evaluate_model_dispatcher = evaluate_model_dispatcher
        self._table_routing_resolver = None
        self._op_ref_cache: TTLCache[tuple[str, str], str] = TTLCache(
            maxsize=50_000, ttl=86_400
        )
        self._op_ref_cache_lock = threading.Lock()
        self._database_ensured = False

        # chDB-specific: all adapters share the same storage path so they
        # see the same databases/tables. chDB's embedded server can only use
        # one path per process, so we use a singleton.
        self._chdb_path = _get_chdb_path(db_path)

    def __del__(self) -> None:
        """Clean up batches on garbage collection.

        Note: we do NOT clean up the temp directory here because chDB's
        background threads may still have files open. Use close() for
        explicit cleanup.
        """
        if self._call_batch or self._calls_complete_batch or self._file_batch:
            try:
                self._flush_all_batches_in_order()
            except Exception:
                pass
            finally:
                self._file_batch = []
                self._call_batch = []
                self._calls_complete_batch = []
                self._flush_immediately = True

    def close(self) -> None:
        """Explicitly close the server and release resources.

        Note: the shared chDB storage path is NOT cleaned up here since it's
        a process-level singleton shared across all ChdbTraceServer instances.
        """
        # Close any thread-local clients
        if hasattr(self._thread_local, "ch_client"):
            self._thread_local.ch_client.close()
            del self._thread_local.ch_client

    # -- Connection layer overrides --

    @property
    def ch_client(self) -> ChdbClientAdapter:  # type: ignore[override]
        """Returns a thread-local chDB client adapter."""
        if not hasattr(self._thread_local, "ch_client"):
            self._thread_local.ch_client = self._mint_client()
        return self._thread_local.ch_client

    def _mint_client(self) -> ChdbClientAdapter:  # type: ignore[override]
        """Create a new chDB client adapter."""
        client = ChdbClientAdapter(path=self._chdb_path)
        self._ensure_database(client)  # type: ignore[arg-type]
        client.database = self._database
        return client

    def _ensure_database(self, client: ChdbClientAdapter) -> None:  # type: ignore[override]
        """Create the database if it doesn't exist."""
        if self._database_ensured:
            return
        with self._init_lock:
            if self._database_ensured:
                return
            client.command(f"CREATE DATABASE IF NOT EXISTS `{self._database}`")
            self._database_ensured = True

    @contextmanager
    def with_new_client(self) -> Iterator[None]:
        """Context manager to use a new client for operations."""
        client = self._mint_client()
        original_client = self.ch_client
        self._thread_local.ch_client = client
        try:
            yield
        finally:
            self._thread_local.ch_client = original_client

    # -- Properties that disable remote-only features --

    @property
    def kafka_producer(self) -> None:  # type: ignore[override]
        """Kafka is not available in embedded mode."""
        return None

    @property
    def use_distributed_mode(self) -> bool:
        """chDB is always single-node."""
        return False

    @property
    def file_storage_client(self) -> None:  # type: ignore[override]
        """File storage client is not available in embedded mode."""
        return None

    # -- Query layer overrides --
    # The parent class methods (_query, _query_stream, _command, _insert)
    # all go through self.ch_client, which now returns a ChdbClientAdapter.
    # The adapter handles the translation from clickhouse_connect API to chDB API.
    #
    # However, we need to override _query and _query_stream because the parent
    # versions use ddtrace decorators and import clickhouse-specific error handling
    # that references clickhouse_connect exceptions.

    def _query_stream(
        self,
        query: str,
        parameters: dict[str, Any],
        column_formats: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> Iterator[tuple]:
        """Stream query results from chDB."""
        parameters = _process_parameters(parameters)
        try:
            with self.ch_client.query_rows_stream(
                query,
                parameters=parameters,
                column_formats=column_formats,
                use_none=True,
                settings=settings,
            ) as stream:
                yield from stream
        except Exception as e:
            logger.exception(
                "chdb_stream_query_error",
                extra={
                    "error_str": str(e),
                    "query": query,
                    "parameters": parameters,
                },
            )
            raise

    def _query(
        self,
        query: str,
        parameters: dict[str, Any],
        column_formats: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> ChdbQueryResult:  # type: ignore[override]
        """Execute a query against chDB and return results."""
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
                "chdb_query_error",
                extra={
                    "error_str": str(e),
                    "query": query,
                    "parameters": parameters,
                },
            )
            raise
        return res

    def _command(
        self,
        command: str,
        parameters: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        """Execute a DDL/DML command against chDB."""
        processed_params = _process_parameters(parameters) if parameters else None
        try:
            self.ch_client.command(
                command,
                parameters=processed_params,
                settings=settings,
            )
        except Exception as e:
            logger.exception(
                "chdb_command_error",
                extra={
                    "error_str": str(e),
                    "command": command,
                    "parameters": processed_params,
                },
            )
            raise

    def _insert(
        self,
        table: str,
        data: Any,
        column_names: list[str],
        settings: dict[str, Any] | None = None,
        do_sync_insert: bool = False,
    ) -> ChdbQuerySummary:  # type: ignore[override]
        """Insert data into a chDB table."""
        if not data:
            return ChdbQuerySummary()

        try:
            return self.ch_client.insert(
                table, data=data, column_names=column_names, settings=settings
            )
        except Exception as e:
            logger.exception(
                "chdb_insert_error",
                extra={
                    "error_str": str(e),
                    "table": table,
                },
            )
            raise

    # -- Migration --

    def _run_migrations(self) -> None:
        """Run schema migrations using the Cloud migrator (no replication)."""
        logger.info("Running chDB migrations")
        migrator = wf_migrator.get_clickhouse_trace_server_migrator(
            self._mint_client(),  # type: ignore[arg-type]
            replicated=False,
            use_distributed=False,
        )
        migrator.apply_migrations(self._database)

    # -- Methods that reference Kafka --

    def calls_score(self, req: tsi.CallsScoreReq) -> tsi.CallsScoreRes:
        """Scoring requires Kafka, which is not available in embedded mode."""
        raise NotImplementedError(
            "calls_score is not supported in chDB mode (requires Kafka)"
        )

    def _flush_kafka_producer(self) -> None:
        """No-op: Kafka is not available in embedded mode."""
        pass
