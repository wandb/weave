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


# All instance attributes set in ClickHouseTraceServer.__init__.
# Instrumentation (ddtrace, coverage) may add extras — those are ignored.
# If you add a new attribute to __init__, add it here AND decide whether
# _reset_server_state in conftest.py needs to reset it between tests.
KNOWN_SERVER_ATTRS = frozenset(
    {
        "_database",
        "_database_ensured",
        "_evaluate_model_dispatcher",
        "_file_storage_client",
        "_file_storage_client_initialized",
        "_host",
        "_init_lock",
        "_kafka_producer",
        "_model_to_provider_info_map",
        "_op_ref_cache",
        "_op_ref_cache_lock",
        "_password",
        "_placeholder_file_projects",
        "_port",
        "_run_migrations",
        "_table_routing_resolver",
        "_thread_local",
        "_use_async_insert",
        "_user",
    }
)


def test_reset_server_state_covers_all_attrs(ch_server):
    """Fails when ClickHouseTraceServer gains new instance attributes.

    Instrumentation attrs (ddtrace, coverage) are ignored — only attrs
    missing from KNOWN_SERVER_ATTRS trigger failure.
    """
    # Only check underscore-prefixed attrs (real app state).
    # Instrumentation (ddtrace) injects public-name wrappers like
    # 'objs_query', 'file_create' etc. — ignore those.
    actual = {
        a for a in ch_server.__dict__ if a.startswith("_") and not a.startswith("__")
    }
    unknown = actual - KNOWN_SERVER_ATTRS
    assert not unknown, (
        f"ClickHouseTraceServer has new attributes: {unknown}. "
        f"Add them to KNOWN_SERVER_ATTRS in this file, and check whether "
        f"_reset_server_state in conftest.py needs to reset them."
    )
