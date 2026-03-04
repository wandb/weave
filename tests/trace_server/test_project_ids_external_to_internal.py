import datetime
import uuid
from unittest.mock import MagicMock

from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    DummyIdConverter,
    UserInjectingExternalTraceServer,
    b64,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.external_to_internal_trace_server_adapter import (
    ExternalTraceServer,
)
from weave.trace_server.sqlite_trace_server import SqliteTraceServer


def test_project_ids_external_to_internal_mapping(
    trace_server: UserInjectingExternalTraceServer,
):
    req = tsi.ProjectIdsExternalToInternalReq(
        project_ids=["shawn/project-a", "shawn/project-b", "shawn/project-a"]
    )

    res = trace_server.project_ids_external_to_internal(req)

    assert res.project_id_map == {
        "shawn/project-a": b64("shawn/project-a"),
        "shawn/project-b": b64("shawn/project-b"),
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


def test_calls_complete_converts_wb_run_id_and_user_id():
    """Test that ExternalTraceServer.calls_complete converts wb_run_id and wb_user_id.

    Regression test: calls_complete was missing ext_to_int_run_id conversion,
    causing ValidationError when callers passed external W&B run paths.
    """
    mock_internal = MagicMock()
    mock_internal.calls_complete.return_value = tsi.CallsUpsertCompleteRes()
    idc = DummyIdConverter()
    adapter = ExternalTraceServer(mock_internal, idc)

    ext_project = "entity/project"
    ext_run_id = "my-run-id"
    ext_user_id = "my-user"
    now = datetime.datetime.now(datetime.timezone.utc)

    req = tsi.CallsUpsertCompleteReq(
        batch=[
            tsi.CompletedCallSchemaForInsert(
                project_id=ext_project,
                id=str(uuid.uuid4()),
                trace_id=str(uuid.uuid4()),
                op_name="test_op",
                started_at=now,
                ended_at=now + datetime.timedelta(seconds=1),
                attributes={},
                inputs={},
                output=None,
                summary={"usage": {}, "status_counts": {}},
                wb_run_id=ext_run_id,
                wb_user_id=ext_user_id,
                wb_run_step=7,
                wb_run_step_end=12,
            )
        ]
    )

    adapter.calls_complete(req)

    # Verify the internal server received converted IDs
    called_req = mock_internal.calls_complete.call_args[0][0]
    item = called_req.batch[0]
    assert item.project_id == b64(ext_project)
    assert item.wb_run_id == b64(ext_run_id) + ":" + ext_run_id
    assert item.wb_user_id == b64(ext_user_id)
    # Integer fields pass through unchanged
    assert item.wb_run_step == 7
    assert item.wb_run_step_end == 12


def test_call_start_v2_converts_wb_run_id():
    """Test that ExternalTraceServer.call_start_v2 converts wb_run_id.

    Regression test: call_start_v2 was missing ext_to_int_run_id conversion.
    """
    mock_internal = MagicMock()
    mock_internal.call_start_v2.return_value = tsi.CallStartV2Res(
        id="call-id", trace_id="trace-id"
    )
    idc = DummyIdConverter()
    adapter = ExternalTraceServer(mock_internal, idc)

    ext_project = "entity/project"
    ext_run_id = "v2-run-id"
    now = datetime.datetime.now(datetime.timezone.utc)

    req = tsi.CallStartV2Req(
        start=tsi.StartedCallSchemaForInsert(
            project_id=ext_project,
            id=str(uuid.uuid4()),
            trace_id=str(uuid.uuid4()),
            op_name="test_op",
            started_at=now,
            attributes={},
            inputs={},
            wb_run_id=ext_run_id,
            wb_run_step=3,
        )
    )

    adapter.call_start_v2(req)

    called_req = mock_internal.call_start_v2.call_args[0][0]
    assert called_req.start.project_id == b64(ext_project)
    assert called_req.start.wb_run_id == b64(ext_run_id) + ":" + ext_run_id
    assert called_req.start.wb_run_step == 3
