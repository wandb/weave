from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from tests.trace.server_utils import TEST_ENTITY, find_server_layer
from tests.trace.util import client_is_sqlite
from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    DummyIdConverter,
    UserInjectingExternalTraceServer,
    externalize_trace_server,
)
from tests.trace_server.workers.evaluate_model_test_worker import (
    EvaluateModelTestDispatcher,
)
from weave.trace_server import clickhouse_trace_server_batched
from weave.trace_server import clickhouse_trace_server_migrator as wf_migrator
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.project_version import project_version
from weave.trace_server.secret_fetcher_context import secret_fetcher_context
from weave.trace_server.sqlite_trace_server import SqliteTraceServer

pytest_plugins = ["tests.trace_server.conftest_lib.clickhouse_server"]


@dataclass(frozen=True)
class ClickHouseSessionState:
    """Holds the session-scoped ClickHouse server and its database names."""

    server: clickhouse_trace_server_batched.ClickHouseTraceServer
    management_db: str
    unique_db: str
    # Tables that should be truncated between tests (excludes views)
    truncatable_tables: list[str]


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--trace-server",
            action="store",
            default="clickhouse",
            help="Specify the backend to use: sqlite or clickhouse",
        )
        parser.addoption(
            "--ch",
            "--clickhouse",
            action="store_true",
            help="Use clickhouse server (shorthand for --trace-server=clickhouse)",
        )
        parser.addoption(
            "--sq",
            "--sqlite",
            action="store_true",
            help="Use sqlite server (shorthand for --trace-server=sqlite)",
        )
        parser.addoption(
            "--clickhouse-process",
            action="store",
            default="false",
            help="Use a clickhouse process instead of a container",
        )
        parser.addoption(
            "--remote-http-trace-server",
            action="store",
            default="remote",
            help="Specify the remote HTTP trace server implementation: remote or stainless",
        )
    except ValueError:
        pass


def pytest_collection_modifyitems(config, items):
    # Add the trace_server marker to:
    # 1. All tests in the trace_server directory (regardless of fixture usage)
    # 2. All tests that use the trace_server fixture (for tests outside this directory)
    # Note: Filtering based on remote-http-trace-server flag is handled in tests/trace_server_bindings/conftest.py
    for item in items:
        # Check if the test is in the trace_server directory by checking parent directories
        if "trace_server" in item.path.parts:
            item.add_marker(pytest.mark.trace_server)
        # Also mark tests that use the trace_server fixture (for tests outside this dir)
        elif "trace_server" in item.fixturenames:
            item.add_marker(pytest.mark.trace_server)


def get_trace_server_flag(request):
    if request.config.getoption("--clickhouse"):
        return "clickhouse"
    if request.config.getoption("--sqlite"):
        return "sqlite"
    weave_server_flag = request.config.getoption("--trace-server")

    # When running with `-m "not trace_server"` (e.g. trace_no_server shard),
    # tests that still need a server (via client fixture) should use sqlite
    # since we're not testing the server itself.
    if weave_server_flag == "clickhouse":
        markexpr = request.config.getoption("-m", default=None)
        if markexpr and "not trace_server" in markexpr:
            return "sqlite"

    return weave_server_flag


def get_remote_http_trace_server_flag(request):
    """Get the remote HTTP trace server implementation to use.

    Returns:
        str: Either 'remote' for RemoteHTTPTraceServer or 'stainless' for StainlessRemoteHTTPTraceServer
    """
    return request.config.getoption("--remote-http-trace-server")


@pytest.fixture(autouse=True)
def reset_project_version_cache():
    project_version.reset_project_residence_cache()
    yield
    project_version.reset_project_residence_cache()


def _get_worker_db_suffix(request, default: str = "_test") -> str:
    """Get database suffix for pytest-xdist worker isolation.

    Returns worker-specific suffix like '_w0' for xdist, or `default` for
    single-process runs.
    """
    worker_input = getattr(request.config, "workerinput", None)
    if worker_input is None:
        return default
    worker_id = worker_input.get("workerid", "master")
    return f"_w{worker_id.replace('gw', '')}"


# Tables with migration-seeded data that should NOT be truncated between tests.
SEED_DATA_TABLES = frozenset({"llm_token_prices"})


def _discover_truncatable_tables(ch_client, database: str) -> list[str]:
    """Query system.tables to find non-view tables that can be truncated."""
    result = ch_client.query(
        "SELECT name FROM system.tables "
        f"WHERE database = '{database}' "
        "AND engine NOT IN ('View', 'MaterializedView') "
        "ORDER BY name"
    )
    return [row[0] for row in result.result_rows if row[0] not in SEED_DATA_TABLES]


def _truncate_all_tables(ch_client, database: str, tables: list[str]) -> None:
    """Truncate all data tables in the database for test isolation."""
    for table in tables:
        ch_client.command(f"TRUNCATE TABLE {database}.{table}")


def _reset_server_state(server: ClickHouseTraceServer) -> None:
    """Reset cached/accumulated state on a ClickHouseTraceServer instance.

    IMPORTANT: If you add new cached/mutable state to ClickHouseTraceServer,
    you must reset it here too — otherwise it will leak between tests and cause
    hard-to-debug order-dependent failures.
    """
    # Clear op ref cache
    server._op_ref_cache.clear()
    # Clear placeholder file projects set
    server._placeholder_file_projects.clear()
    # Reset table routing resolver to None so it's lazily re-created
    # (tests may have set _mode to AUTO or accessed the resolver)
    server._table_routing_resolver = None
    # Reset file storage client so tests that mock env vars get a fresh client
    server._file_storage_client = None
    server._file_storage_client_initialized = False
    # Reset batch queues (thread-local, for current thread)
    server._call_batch = []
    server._file_batch = []
    server._calls_complete_batch = []
    server._flush_immediately = False


@pytest.fixture(scope="session")
def _ch_session_server(
    ensure_clickhouse_db,
    request,
) -> ClickHouseSessionState | None:
    """Session-scoped ClickHouse server: created once, migrated once.

    Returns None if ClickHouse is not the selected backend, so that
    function-scoped fixtures can fall through to the old path if needed.
    """
    # Only set up if we'll actually use clickhouse
    trace_server_flag = request.config.getoption("--trace-server", default="clickhouse")
    use_sqlite = request.config.getoption("--sqlite", default=False)
    if use_sqlite or trace_server_flag == "sqlite":
        yield None
        return

    host, port = next(ensure_clickhouse_db())
    db_suffix = _get_worker_db_suffix(request)

    original_db = os.environ.get("WF_CLICKHOUSE_DATABASE")
    base_db = original_db or "default"
    unique_db = f"{base_db}{db_suffix}"
    management_db = f"db_management{db_suffix}"

    os.environ["WF_CLICKHOUSE_DATABASE"] = unique_db

    id_converter = DummyIdConverter()
    ch_server = clickhouse_trace_server_batched.ClickHouseTraceServer(
        host=host,
        port=port,
        database=unique_db,
        evaluate_model_dispatcher=EvaluateModelTestDispatcher(
            id_converter=id_converter
        ),
    )

    # Drop and recreate from scratch once
    ch_server.ch_client.command(f"DROP DATABASE IF EXISTS {management_db}")
    ch_server.ch_client.command(f"DROP DATABASE IF EXISTS {unique_db}")
    ch_server._database_ensured = False

    def patched_run_migrations():
        migrator = wf_migrator.get_clickhouse_trace_server_migrator(
            ch_server._mint_client(), management_db=management_db
        )
        migrator.apply_migrations(ch_server._database)

    ch_server._run_migrations = patched_run_migrations  # type: ignore[assignment]
    ch_server._run_migrations()

    truncatable = _discover_truncatable_tables(ch_server.ch_client, unique_db)

    yield ClickHouseSessionState(
        server=ch_server,
        management_db=management_db,
        unique_db=unique_db,
        truncatable_tables=truncatable,
    )

    # Restore env
    if original_db is None:
        os.environ.pop("WF_CLICKHOUSE_DATABASE", None)
    else:
        os.environ["WF_CLICKHOUSE_DATABASE"] = original_db

    # Session cleanup: drop databases
    try:
        ch_server.ch_client.command(f"DROP DATABASE IF EXISTS {management_db}")
    except Exception:
        pass
    try:
        ch_server.ch_client.command(f"DROP DATABASE IF EXISTS {unique_db}")
    except Exception:
        pass
    try:
        ch_server.ch_client.close()
    except Exception:
        pass


@pytest.fixture
def get_ch_trace_server(
    _ch_session_server: ClickHouseSessionState | None,
    request,
) -> Callable[[], UserInjectingExternalTraceServer]:
    """Function-scoped CH fixture factory. Reuses session-scoped DB, truncates between tests."""

    def ch_trace_server_inner() -> UserInjectingExternalTraceServer:
        if _ch_session_server is None:
            pytest.skip("ClickHouse session not available")

        state = _ch_session_server
        server = state.server

        # Truncate all tables for a clean slate
        _truncate_all_tables(
            server.ch_client, state.unique_db, state.truncatable_tables
        )

        # Reset any accumulated in-memory state
        _reset_server_state(server)

        # Force synchronous writes so tests see data immediately
        server._flush_immediately = True

        # Wrap in the external adapter (fresh id_converter per test)
        id_converter = DummyIdConverter()
        server._evaluate_model_dispatcher = EvaluateModelTestDispatcher(
            id_converter=id_converter
        )
        return externalize_trace_server(server, TEST_ENTITY, id_converter=id_converter)

    return ch_trace_server_inner


@pytest.fixture
def get_sqlite_trace_server(
    request,
) -> Callable[[], UserInjectingExternalTraceServer]:
    servers_to_cleanup: list[SqliteTraceServer] = []

    def sqlite_trace_server_inner() -> UserInjectingExternalTraceServer:
        id_converter = DummyIdConverter()
        # Use worker-specific database for pytest-xdist isolation
        # Each worker gets its own isolated database
        db_suffix = _get_worker_db_suffix(request)
        if db_suffix:
            # Use worker-specific in-memory database name for parallel execution
            db_path = f"file::memory:?cache=shared&name=test{db_suffix}"
        else:
            # Single worker or sequential execution - use default shared memory
            db_path = "file::memory:?cache=shared"
        sqlite_server = SqliteTraceServer(
            db_path,
            evaluate_model_dispatcher=EvaluateModelTestDispatcher(
                id_converter=id_converter
            ),
        )
        # Track server for cleanup
        servers_to_cleanup.append(sqlite_server)

        sqlite_server.drop_tables()
        sqlite_server.setup_tables()
        return externalize_trace_server(
            sqlite_server, TEST_ENTITY, id_converter=id_converter
        )

    yield sqlite_trace_server_inner

    # Cleanup after all tests using this fixture complete
    for sqlite_server in servers_to_cleanup:
        try:
            # Drop tables to ensure clean shutdown
            sqlite_server.drop_tables()
        except Exception:
            pass  # Best effort cleanup
        try:
            sqlite_server.close()
        except Exception:
            pass  # Best effort cleanup


class LocalSecretFetcher:
    def fetch(self, secret_name: str) -> dict:
        return {"secrets": {secret_name: os.getenv(secret_name)}}


@pytest.fixture
def local_secret_fetcher():
    with secret_fetcher_context(LocalSecretFetcher()):
        yield


@pytest.fixture
def trace_server(
    request, local_secret_fetcher, get_ch_trace_server, get_sqlite_trace_server
) -> UserInjectingExternalTraceServer:
    trace_server_flag = get_trace_server_flag(request)
    if trace_server_flag == "clickhouse":
        return get_ch_trace_server()
    elif trace_server_flag == "sqlite":
        return get_sqlite_trace_server()
    else:
        # Once we split the trace server and client code, we can raise here.
        # For now, just return the sqlite trace server so we don't break existing tests.
        # raise ValueError(f"Invalid trace server: {trace_server_flag}")
        return get_sqlite_trace_server()


@pytest.fixture
def ch_server(trace_server):
    """Extract ClickHouseTraceServer from the test fixture, or skip."""
    server = trace_server._internal_trace_server
    if not isinstance(server, ClickHouseTraceServer):
        pytest.skip("ClickHouse-only test")
    return server


@pytest.fixture
def internal_server(client):
    """Return the underlying SQLite or ClickHouse server from the middleware chain."""
    if client_is_sqlite(client):
        return find_server_layer(client.server, SqliteTraceServer)
    return find_server_layer(client.server, ClickHouseTraceServer)
