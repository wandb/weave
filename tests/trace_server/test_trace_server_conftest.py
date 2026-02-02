import pytest

from tests.trace_server.conftest import get_trace_server_flag
from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    TestOnlyUserInjectingExternalTraceServer,
)
from weave.trace_server.clickhouse_query_layer.trace_server import ClickHouseTraceServer
from weave.trace_server.sqlite_trace_server import SqliteTraceServer


def test_trace_server_fixture(
    request, trace_server: TestOnlyUserInjectingExternalTraceServer
):
    assert isinstance(trace_server, TestOnlyUserInjectingExternalTraceServer)
    if get_trace_server_flag(request) == "clickhouse":
        assert isinstance(trace_server._internal_trace_server, ClickHouseTraceServer)
    else:
        assert isinstance(trace_server._internal_trace_server, SqliteTraceServer)


@pytest.mark.skip_clickhouse_client
def test_skip_clickhouse_client(
    request, trace_server: TestOnlyUserInjectingExternalTraceServer
):
    assert isinstance(trace_server, TestOnlyUserInjectingExternalTraceServer)
    assert get_trace_server_flag(request) != "clickhouse"
