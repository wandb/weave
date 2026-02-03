from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

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
from weave.trace_server.clickhouse_query_layer import (
    trace_server as clickhouse_trace_server_batched,
)
from weave.trace_server.project_version import project_version
from weave.trace_server.secret_fetcher_context import secret_fetcher_context
from weave.trace_server.sqlite_trace_server import SqliteTraceServer

TEST_ENTITY = "shawn"


@dataclass(frozen=True)
class ClickHouseServerCleanup:
    """Tracks ClickHouse server resources that need cleanup after tests."""

    server: clickhouse_trace_server_batched.ClickHouseTraceServer
    management_db: str
    unique_db: str


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
    servers_to_cleanup: list[ClickHouseServerCleanup] = []

    def ch_trace_server_inner() -> TestOnlyUserInjectingExternalTraceServer:
        host, port = next(ensure_clickhouse_db())
        db_suffix = _get_worker_db_suffix(request)

        # Always add a test-specific suffix to prevent collision with other databases
        if not db_suffix:
            db_suffix = "_test"

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

            # Track server for cleanup
            servers_to_cleanup.append(
                ClickHouseServerCleanup(
                    server=ch_server,
                    management_db=management_db,
                    unique_db=unique_db,
                )
            )

            # Clean up any existing worker-specific databases
            ch_server.ch_client.command(f"DROP DATABASE IF EXISTS {management_db}")
            ch_server.ch_client.command(f"DROP DATABASE IF EXISTS {unique_db}")

            # Patch run_migrations to use worker-specific management database
            def patched_run_migrations():
                from weave.trace_server.clickhouse_query_layer import (
                    migrator as wf_migrator,
                )

                migrator = wf_migrator.get_clickhouse_trace_server_migrator(
                    ch_server._ch_client._mint_client(), management_db=management_db
                )
                migrator.apply_migrations(ch_server._ch_client._database)

            ch_server._ch_client.run_migrations = patched_run_migrations  # type: ignore[assignment]
            ch_server._ch_client.run_migrations()

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

    yield ch_trace_server_inner

    # Cleanup after all tests using this fixture complete
    for server_config in servers_to_cleanup:
        ch_client = getattr(server_config.server, "ch_client", None)
        if not ch_client:
            continue

        # Drop test databases (best effort)
        try:
            ch_client.command(f"DROP DATABASE IF EXISTS {server_config.management_db}")
        except Exception:
            pass

        try:
            ch_client.command(f"DROP DATABASE IF EXISTS {server_config.unique_db}")
        except Exception:
            pass

        # Close client connection (best effort)
        try:
            ch_client.close()
        except Exception:
            pass


@pytest.fixture
def get_sqlite_trace_server(
    request,
) -> Callable[[], TestOnlyUserInjectingExternalTraceServer]:
    servers_to_cleanup: list[SqliteTraceServer] = []

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
) -> TestOnlyUserInjectingExternalTraceServer:
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
