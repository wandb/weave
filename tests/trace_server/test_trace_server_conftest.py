import pytest

from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    TestOnlyUserInjectingExternalTraceServer,
)
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.sqlite_trace_server import SqliteTraceServer


def test_trace_server_fixture(
    request, trace_server: TestOnlyUserInjectingExternalTraceServer
):
    assert isinstance(trace_server, TestOnlyUserInjectingExternalTraceServer)
    if request.config.getoption("--trace-server") == "clickhouse":
        assert isinstance(trace_server._internal_trace_server, ClickHouseTraceServer)
    else:
        assert isinstance(trace_server._internal_trace_server, SqliteTraceServer)


@pytest.mark.skip_clickhouse_client
def test_skip_clickhouse_client(
    request, trace_server: TestOnlyUserInjectingExternalTraceServer
):
    assert isinstance(trace_server, TestOnlyUserInjectingExternalTraceServer)
    assert request.config.getoption("--trace-server") != "clickhouse"
