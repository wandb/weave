from collections.abc import Generator
from typing import Callable

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
from weave.trace_server import environment as ts_env
from weave.trace_server.secret_fetcher_context import secret_fetcher_context
from weave.trace_server.sqlite_trace_server import SqliteTraceServer

TEST_ENTITY = "shawn"


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--trace-server",
            action="store",
            default="clickhouse",
            help="Specify the client object to use: sqlite or clickhouse",
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
    weave_server_flag = request.config.getoption("--trace-server")
    return weave_server_flag


@pytest.fixture
def get_ch_trace_server(
    ensure_clickhouse_db,
) -> Callable[[], TestOnlyUserInjectingExternalTraceServer]:
    def ch_trace_server_inner() -> TestOnlyUserInjectingExternalTraceServer:
        host, port = next(ensure_clickhouse_db())
        id_converter = DummyIdConverter()
        ch_server = clickhouse_trace_server_batched.ClickHouseTraceServer(
            host=host,
            port=port,
            evaluate_model_dispatcher=EvaluateModelTestDispatcher(
                id_converter=id_converter
            ),
        )
        ch_server.ch_client.command("DROP DATABASE IF EXISTS db_management")
        ch_server.ch_client.command(
            f"DROP DATABASE IF EXISTS {ts_env.wf_clickhouse_database()}"
        )
        ch_server._run_migrations()

        return externalize_trace_server(
            ch_server, TEST_ENTITY, id_converter=id_converter
        )

    return ch_trace_server_inner


@pytest.fixture
def get_sqlite_trace_server() -> Callable[[], TestOnlyUserInjectingExternalTraceServer]:
    def sqlite_trace_server_inner() -> TestOnlyUserInjectingExternalTraceServer:
        id_converter = DummyIdConverter()
        sqlite_server = SqliteTraceServer(
            "file::memory:?cache=shared",
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
) -> Generator[TestOnlyUserInjectingExternalTraceServer, None, None]:
    trace_server_flag = get_trace_server_flag(request)
    if trace_server_flag == "clickhouse":
        server = get_ch_trace_server()
        yield server
    elif trace_server_flag == "sqlite":
        server = get_sqlite_trace_server()
        try:
            yield server
        finally:
            # Close SQLite database connection to prevent resource leaks
            if hasattr(server, "_internal_trace_server"):
                internal_server = server._internal_trace_server
                if isinstance(internal_server, SqliteTraceServer):
                    internal_server.close()
    else:
        # Once we split the trace server and client code, we can raise here.
        # For now, just return the sqlite trace server so we don't break existing tests.
        # raise ValueError(f"Invalid trace server: {trace_server_flag}")
        server = get_sqlite_trace_server()
        try:
            yield server
        finally:
            # Close SQLite database connection to prevent resource leaks
            if hasattr(server, "_internal_trace_server"):
                internal_server = server._internal_trace_server
                if isinstance(internal_server, SqliteTraceServer):
                    internal_server.close()
