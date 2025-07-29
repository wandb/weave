from collections.abc import Callable

import pytest

from tests.trace_server.conftest_lib.clickhouse_server import *
from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    TestOnlyUserInjectingExternalTraceServer,
    externalize_trace_server,
)
from weave.trace_server import clickhouse_trace_server_batched
from weave.trace_server import environment as ts_env
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
            "--clickhouse-process",
            action="store",
            default="false",
            help="Use a clickhouse process instead of a container",
        )
    except ValueError:
        pass


def pytest_collection_modifyitems(config, items):
    # Add the trace_server marker to all tests that have a client fixture
    for item in items:
        if "trace_server" in item.fixturenames:
            item.add_marker(pytest.mark.trace_server)


def get_trace_server_flag(request):
    if request.config.getoption("--clickhouse"):
        return "clickhouse"
    weave_server_flag = request.config.getoption("--trace-server")
    return weave_server_flag


@pytest.fixture
def get_ch_trace_server(
    ensure_clickhouse_db,
) -> Callable[[], TestOnlyUserInjectingExternalTraceServer]:
    def ch_trace_server_inner() -> TestOnlyUserInjectingExternalTraceServer:
        host, port = next(ensure_clickhouse_db())

        ch_server = clickhouse_trace_server_batched.ClickHouseTraceServer(
            host=host,
            port=port,
        )
        ch_server.ch_client.command("DROP DATABASE IF EXISTS db_management")
        ch_server.ch_client.command(
            f"DROP DATABASE IF EXISTS {ts_env.wf_clickhouse_database()}"
        )
        ch_server._run_migrations()

        return externalize_trace_server(ch_server, TEST_ENTITY)

    return ch_trace_server_inner


@pytest.fixture
def get_sqlite_trace_server() -> Callable[[], TestOnlyUserInjectingExternalTraceServer]:
    def sqlite_trace_server_inner() -> TestOnlyUserInjectingExternalTraceServer:
        sqlite_server = SqliteTraceServer("file::memory:?cache=shared")
        sqlite_server.drop_tables()
        sqlite_server.setup_tables()
        return externalize_trace_server(sqlite_server, TEST_ENTITY)

    return sqlite_trace_server_inner


@pytest.fixture
def trace_server(
    request, get_ch_trace_server, get_sqlite_trace_server
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
