import datetime
import uuid

from weave.trace import weave_client
from weave.trace_server import trace_server_interface as tsi


def test_call_update_out_of_order(client: weave_client.WeaveClient):
    # Here, we are going to do an out of order sequence:
    # 1. Name a call
    # 2. Finish the call
    # 3. Start the call
    # 4. Delete the call
    #
    # Only step 3 should actually have the result in the query.

    call_id = str(uuid.uuid4())
    project_id = client._project_id()

    def get_calls():
        res = client.server.calls_query(
            tsi.CallsQueryReq(
                project_id=project_id,
            )
        )
        return res.calls

    client.server.call_update(
        tsi.CallUpdateReq(
            project_id=project_id,
            call_id=call_id,
            display_name="test_display_name",
        )
    )

    assert len(get_calls()) == 0

    client.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                ended_at=datetime.datetime.now(),
                exception=None,
                output=None,
                summary={},
            )
        )
    )

    assert len(get_calls()) == 0

    client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=call_id,
                started_at=datetime.datetime.now(),
                op_name="test_op_name",
                attributes={},
                inputs={},
            )
        )
    )

    assert len(get_calls()) == 1

    client.server.calls_delete(
        tsi.CallsDeleteReq(
            project_id=project_id,
            call_ids=[call_id],
        )
    )

    assert len(get_calls()) == 0
