from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


def test_actions_query(client: WeaveClient):
    server = client.server
    res = server.actions_execute_batch(
        tsi.ActionsExecuteBatchReq(
            project_id=client.project, call_ids=["1", "2"], id="1"
        )
    )
    assert res.id == "1"
