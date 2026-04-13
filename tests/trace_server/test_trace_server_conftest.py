import pytest

from tests.trace_server.conftest import get_trace_server_flag
from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    UserInjectingExternalTraceServer,
)
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.sqlite_trace_server import SqliteTraceServer


def test_trace_server_fixture(request, trace_server: UserInjectingExternalTraceServer):
    assert isinstance(trace_server, UserInjectingExternalTraceServer)
    if get_trace_server_flag(request) == "clickhouse":
        assert isinstance(trace_server._internal_trace_server, ClickHouseTraceServer)
    else:
        assert isinstance(trace_server._internal_trace_server, SqliteTraceServer)


@pytest.mark.skip_clickhouse_client
def test_skip_clickhouse_client(
    request, trace_server: UserInjectingExternalTraceServer
):
    assert isinstance(trace_server, UserInjectingExternalTraceServer)
    assert get_trace_server_flag(request) != "clickhouse"


# The exact count of instance attributes on ClickHouseTraceServer.__init__.
# If this changes, someone added or removed state. The test below will fail
# and force them to check whether _reset_server_state needs updating.
EXPECTED_ATTR_COUNT = 19


def test_reset_server_state_covers_all_attrs(ch_server):
    """Canary: fails when ClickHouseTraceServer gains/loses instance attributes.

    This doesn't know *which* attributes need resetting — it just notices when
    the set changes so the author is forced to check _reset_server_state.
    """
    attr_count = len([a for a in ch_server.__dict__ if not a.startswith("__")])
    assert attr_count == EXPECTED_ATTR_COUNT, (
        f"ClickHouseTraceServer has {attr_count} instance attributes "
        f"(expected {EXPECTED_ATTR_COUNT}). If you added/removed state, "
        f"check whether _reset_server_state in conftest.py needs updating, "
        f"then update EXPECTED_ATTR_COUNT."
    )
