from concurrent.futures import Future

import weave
from weave.trace.feedback_types.score import SCORE_TYPE_NAME
from weave.trace.weave_client import get_ref
from weave.trace_server import trace_server_interface as tsi


def test_send_score_call(client):
    @weave.op
    def my_op(x: int) -> int:
        return x + 1

    @weave.op
    def my_score(input_x: int, model_output: int) -> int:
        return {"in_range": input_x < model_output}

    # Invoke the op
    call_res, call = my_op.call(1)
    assert call_res == 2

    # Score the results
    score_res, score_call = my_score.call(1, call_res)
    assert score_res == {"in_range": True}

    # Store the score as feedback on the call
    res_fut = client._send_score_call(call, score_call)
    assert isinstance(res_fut, Future)
    res = res_fut.result()
    assert isinstance(res, str)

    query_res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            include_feedback=True,
        )
    )
    calls = query_res.calls

    assert len(calls) == 2
    feedback = calls[0].summary["weave"]["feedback"][0]
    assert feedback["feedback_type"] == SCORE_TYPE_NAME
    assert feedback["weave_ref"] == get_ref(call).uri()
    assert feedback["payload"]["name"] == "my_score"
    assert feedback["payload"]["op_ref"] == get_ref(my_score).uri()
    assert feedback["payload"]["call_ref"] == get_ref(score_call).uri()
    assert feedback["payload"]["results"] == score_res
