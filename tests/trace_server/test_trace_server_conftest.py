import base64
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.trace_server.conftest import get_trace_server_flag
from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    UserInjectingExternalTraceServer,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.errors import NotFoundError
from weave.trace_server.external_to_internal_trace_server_adapter import (
    ExternalTraceServer,
    IdConverter,
)
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


# --- ExternalTraceServer mutation-invariance regression ---
# Before #6670, the adapter mutated `req.project_id` in place when
# translating external entity/project strings to internal base64 form.
# A retry layer above the adapter would re-invoke the same `req`, which
# now held an already-internal project_id, and the adapter would encode
# it a second time — producing base64(base64(...)) garbage and querying
# a nonexistent project. Parametrized across several methods covering
# the different mutation shapes (flat, nested obj/table, nested
# start/end, filter-carrying) so we don't regress on any of them.


class _EncodingIdConverter(IdConverter):
    """Base64 ext<->int just like the real converter, so double-encoding
    would be observable as a materially different string.
    """

    def ext_to_int_project_id(self, project_id: str) -> str:
        return base64.b64encode(project_id.encode()).decode()

    def int_to_ext_project_id(self, project_id: str) -> str | None:
        try:
            return base64.b64decode(project_id.encode()).decode()
        except Exception:
            return None

    def ext_to_int_run_id(self, run_id: str) -> str:
        return run_id

    def int_to_ext_run_id(self, run_id: str) -> str:
        return run_id

    def ext_to_int_user_id(self, user_id: str) -> str:
        return user_id

    def int_to_ext_user_id(self, user_id: str) -> str:
        return user_id


@pytest.mark.parametrize(
    ("method_name", "req_factory"),
    [
        (
            "obj_read",
            lambda: tsi.ObjReadReq(project_id="ent/proj", object_id="o", digest="d"),
        ),
        (
            "obj_create",
            lambda: tsi.ObjCreateReq(
                obj=tsi.ObjSchemaForInsert(
                    project_id="ent/proj", object_id="o", val={}, wb_user_id="u"
                )
            ),
        ),
        (
            "table_create",
            lambda: tsi.TableCreateReq(
                table=tsi.TableSchemaForInsert(project_id="ent/proj", rows=[])
            ),
        ),
        (
            "file_content_read",
            lambda: tsi.FileContentReadReq(project_id="ent/proj", digest="d"),
        ),
        (
            "calls_query",
            lambda: tsi.CallsQueryReq(
                project_id="ent/proj",
                filter=tsi.CallsFilter(wb_user_ids=["user-x"], wb_run_ids=["run-y"]),
            ),
        ),
    ],
)
def test_adapter_does_not_mutate_req_when_inner_raises(
    method_name: str, req_factory: Callable[[], Any]
) -> None:
    """Regression for the adapter-mutates-req bug. On failure, the
    caller's `req` must be byte-identical so a retry layer above can
    re-invoke with the original external project_id.
    """
    inner = MagicMock(spec=tsi.FullTraceServerInterface)
    getattr(inner, method_name).side_effect = NotFoundError("test")
    adapter = ExternalTraceServer(inner, _EncodingIdConverter())

    req = req_factory()
    snapshot = req.model_dump()

    with pytest.raises(NotFoundError):
        getattr(adapter, method_name)(req)

    assert req.model_dump() == snapshot
