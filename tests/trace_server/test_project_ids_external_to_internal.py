from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    UserInjectingExternalTraceServer,
    b64,
)
from weave.trace_server import trace_server_interface as tsi


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
