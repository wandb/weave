from typing import Generator
import pytest
from tests.trace_server.conftest_lib.clickhouse_server import ensure_clickhouse_db
from tests.trace_server.conftest_lib.trace_server_external_adapter import externalize_trace_server
from weave.trace_server import clickhouse_trace_server_batched
from weave.trace_server import environment as ts_env
from weave.trace_server import trace_server_interface as tsi

TEST_ENTITY = "shawn"

def pytest_addoption(parser):
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

def get_trace_server_flag(request):
    if request.config.getoption("--clickhouse"):
        return "clickhouse"
    weave_server_flag = request.config.getoption("--trace-server")
    return weave_server_flag

@pytest.fixture
def ch_internal_trace_server(request) -> tsi.TraceServerInterface:
    assert ensure_clickhouse_db is not None
    host, port = request.getfixturevalue("ensure_clickhouse_db")

    ch_server = clickhouse_trace_server_batched.ClickHouseTraceServer(
        host=host,
        port=port,
    )
    ch_server.ch_client.command("DROP DATABASE IF EXISTS db_management")
    ch_server.ch_client.command(
        f"DROP DATABASE IF EXISTS {ts_env.wf_clickhouse_database()}"
    )
    ch_server._run_migrations()

    return ch_server


@pytest.fixture
def ch_trace_server(request) -> Generator[tsi.TraceServerInterface, None, None]:
    trace_server_flag = get_trace_server_flag(request)
    if trace_server_flag != "clickhouse":
        pytest.skip("Clickhouse trace server is not available")
    server = request.getfixturevalue("ch_internal_trace_server")
    yield externalize_trace_server(server, TEST_ENTITY)

@pytest.fixture
def sqlite_trace_server(request) -> Generator[tsi.TraceServerInterface, None, None]:
    trace_server_flag = get_trace_server_flag(request)
    if trace_server_flag != "sqlite":
        pytest.skip("Sqlite trace server is not available")
    sqlite_server = sqlite_trace_server.SqliteTraceServer(
        "file::memory:?cache=shared"
    )
    sqlite_server.drop_tables()
    sqlite_server.setup_tables()
    yield externalize_trace_server(sqlite_server, TEST_ENTITY)

@pytest.fixture
def trace_server(request) -> tsi.TraceServerInterface:
    trace_server_flag = get_trace_server_flag(request)
    if trace_server_flag == "clickhouse":
        return request.getfixturevalue("ch_trace_server")
    elif trace_server_flag == "sqlite":
        return request.getfixturevalue("sqlite_trace_server")
    else:
        raise ValueError(f"Invalid trace server: {trace_server_flag}")