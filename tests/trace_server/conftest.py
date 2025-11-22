import os
from collections.abc import Callable

import pytest

from tests.trace_server.conftest_lib.clickhouse_server import *
from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    DummyIdConverter,
    TestOnlyUserInjectingExternalTraceServer,
    externalize_trace_server,
)
from tests.trace_server.workers.evaluate_model_test_worker import (
    EvaluateModelTestDispatcher,
)
from weave.trace_server import clickhouse_trace_server_batched
from weave.trace_server.secret_fetcher_context import secret_fetcher_context
from weave.trace_server.sqlite_trace_server import SqliteTraceServer

TEST_ENTITY = "shawn"


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--trace-server",
            action="store",
            default="mock",
            help="Specify the client object to use: mock, sqlite or clickhouse",
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
            "--mock",
            action="store_true",
            help="Use mock server (shorthand for --trace-server=mock)",
        )
        parser.addoption(
            "--clickhouse-process",
            action="store",
            default="false",
            help="Use a clickhouse process instead of a container",
        )
    except ValueError:
        pass


def pytest_collection_modifyitems(config, items):
    # Add the trace_server marker to:
    # 1. All tests in the trace_server directory (regardless of fixture usage)
    # 2. All tests that use the trace_server fixture (for tests outside this directory)
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
    if request.config.getoption("--mock"):
        return "mock"
    weave_server_flag = request.config.getoption("--trace-server")
    return weave_server_flag


def _get_worker_db_suffix(request) -> str:
    """Get database suffix for pytest-xdist worker isolation."""
    worker_input = getattr(request.config, "workerinput", None)
    if worker_input is None:
        return ""
    worker_id = worker_input.get("workerid", "master")
    return f"_w{worker_id.replace('gw', '')}"


@pytest.fixture
def get_ch_trace_server(
    ensure_clickhouse_db,
    request,
) -> Callable[[], TestOnlyUserInjectingExternalTraceServer]:
    def ch_trace_server_inner() -> TestOnlyUserInjectingExternalTraceServer:
        host, port = next(ensure_clickhouse_db())
        db_suffix = _get_worker_db_suffix(request)

        # Store original environment variable
        original_db = os.environ.get("WF_CLICKHOUSE_DATABASE")
        base_db = original_db or "default"
        unique_db = f"{base_db}{db_suffix}"
        management_db = f"db_management{db_suffix}"

        # Set worker-specific database name
        os.environ["WF_CLICKHOUSE_DATABASE"] = unique_db

        try:
            id_converter = DummyIdConverter()
            ch_server = clickhouse_trace_server_batched.ClickHouseTraceServer(
                host=host,
                port=port,
                database=unique_db,
                evaluate_model_dispatcher=EvaluateModelTestDispatcher(
                    id_converter=id_converter
                ),
            )

            # Clean up any existing worker-specific databases
            ch_server.ch_client.command(f"DROP DATABASE IF EXISTS {management_db}")
            ch_server.ch_client.command(f"DROP DATABASE IF EXISTS {unique_db}")

            # Patch _run_migrations to use worker-specific management database
            def patched_run_migrations():
                import weave.trace_server.clickhouse_trace_server_migrator as wf_migrator

                migrator = wf_migrator.ClickHouseTraceServerMigrator(
                    ch_server._mint_client(), management_db=management_db
                )
                migrator.apply_migrations(ch_server._database)

            ch_server._run_migrations = patched_run_migrations  # type: ignore[assignment]
            ch_server._run_migrations()

            result = externalize_trace_server(
                ch_server, TEST_ENTITY, id_converter=id_converter
            )
            return result
        finally:
            # Restore original database name
            if original_db is None:
                os.environ.pop("WF_CLICKHOUSE_DATABASE", None)
            else:
                os.environ["WF_CLICKHOUSE_DATABASE"] = original_db

    return ch_trace_server_inner


@pytest.fixture
def get_sqlite_trace_server(
    request,
) -> Callable[[], TestOnlyUserInjectingExternalTraceServer]:
    def sqlite_trace_server_inner() -> TestOnlyUserInjectingExternalTraceServer:
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
        sqlite_server.drop_tables()
        sqlite_server.setup_tables()
        return externalize_trace_server(
            sqlite_server, TEST_ENTITY, id_converter=id_converter
        )

    return sqlite_trace_server_inner


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
) -> TestOnlyUserInjectingExternalTraceServer:
    trace_server_flag = get_trace_server_flag(request)
    if trace_server_flag == "clickhouse":
        return get_ch_trace_server()
    elif trace_server_flag == "sqlite":
        return get_sqlite_trace_server()
    elif trace_server_flag == "mock":
        # Import here to avoid circular dependency
        from tests.mock_trace_server import MockTraceServer
        return MockTraceServer()
    else:
        # Default to mock for unknown options
        from tests.mock_trace_server import MockTraceServer
        return MockTraceServer()
