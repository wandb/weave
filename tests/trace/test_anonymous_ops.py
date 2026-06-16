import pytest

from tests.trace.util import FAKE_NOT_IMPLEMENTED
from weave.trace import weave_client
from weave.trace_server.trace_server_interface import CallsQueryReq


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_anonymous_op(client: weave_client.WeaveClient) -> str:
    call = client.create_call("anonymous_op", {"a": 1})
    client.finish_call(call, {"c": 3}, None)

    call_res = client.server.calls_query(
        CallsQueryReq(
            project_id=client.project_id,
        )
    )
    calls = call_res.calls

    assert len(calls) == 1
    call = calls[0]
    assert (
        call.op_name
        == "weave:///shawn/test-project/op/anonymous_op:6jAV4T6F42RKlabeB2RO0BXkbFFPrKyU2yyQedpotB8"
    )
    assert call.inputs == {"a": 1}
    assert call.output == {"c": 3}
    assert call.exception is None


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_anonymous_op_with_config(client: weave_client.WeaveClient) -> str:
    call = client.create_call(
        weave_client._build_anonymous_op("anonymous_op", {"library_version": "0.42.0"}),
        {"a": 1},
    )
    client.finish_call(call, {"c": 3}, None)

    call_res = client.server.calls_query(
        CallsQueryReq(
            project_id=client.project_id,
        )
    )
    calls = call_res.calls

    assert len(calls) == 1
    call = calls[0]
    assert (
        call.op_name
        == "weave:///shawn/test-project/op/anonymous_op:Cyx5COqtd8xacHG6PNdYf0FfanjItQehqapU71HLoFk"
    )
    assert call.inputs == {"a": 1}
    assert call.output == {"c": 3}
    assert call.exception is None
