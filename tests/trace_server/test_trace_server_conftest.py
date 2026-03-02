import pytest

from tests.trace_server.conftest import get_trace_server_flag
from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    TestOnlyUserInjectingExternalTraceServer,
    b64,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
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


def test_project_ids_external_to_internal_mapping(
    trace_server: TestOnlyUserInjectingExternalTraceServer,
):
    req = tsi.ProjectIdsExternalToInternalReq(
        project_ids=["shawn/project-a", "shawn/project-b", "shawn/project-a"]
    )

    res = trace_server.project_ids_external_to_internal(req)

    assert res.project_id_map == {
        b64("shawn/project-a"): "shawn/project-a",
        b64("shawn/project-b"): "shawn/project-b",
    }


def test_sqlite_project_ids_external_to_internal_passthrough():
    sqlite_server = SqliteTraceServer("file::memory:?cache=shared")
    req = tsi.ProjectIdsExternalToInternalReq(
        project_ids=["internal-project-a", "internal-project-b", "internal-project-a"]
    )

    try:
        res = sqlite_server.project_ids_external_to_internal(req)
    finally:
        sqlite_server.close()

    assert res.project_id_map == {
        "internal-project-a": "internal-project-a",
        "internal-project-b": "internal-project-b",
    }
