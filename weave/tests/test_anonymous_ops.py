from weave import weave_client
from weave.trace_server.trace_server_interface import CallsQueryReq


def test_named_op(client: weave_client.WeaveClient) -> str:
    call = client.create_call("anonymous_op", {"a": 1})
    client.finish_call(call, {"c": 3}, None)

    call_res = client.server.calls_query(
        CallsQueryReq(
            project_id=client._project_id(),
        )
    )
    calls = call_res.calls

    assert len(calls) == 1
    call = calls[0]
    assert (
        call.op_name
        == "weave:///shawn/test-project/op/anonymous_op:tzUhDyzVm5bqQsuqh5RT4axEXSosyLIYZn9zbRyenaw"
    )
    assert call.inputs == {"a": 1}
    assert call.output == {"c": 3}
    assert call.exception is None


def test_anonymous_op(client: weave_client.WeaveClient) -> str:
    call = client.create_call("anonymous_op", {"a": 1})
    client.finish_call(call, {"c": 3}, None)

    call_res = client.server.calls_query(
        CallsQueryReq(
            project_id=client._project_id(),
        )
    )
    calls = call_res.calls

    assert len(calls) == 1
    call = calls[0]
    assert (
        call.op_name
        == "weave:///shawn/test-project/op/anonymous_op:tzUhDyzVm5bqQsuqh5RT4axEXSosyLIYZn9zbRyenaw"
    )
    assert call.inputs == {"a": 1}
    assert call.output == {"c": 3}
    assert call.exception is None


def test_anonymous_op_with_config(client: weave_client.WeaveClient) -> str:
    call = client.create_call(
        weave_client._build_anonymous_op("anonymous_op", {"library_version": "0.42.0"}),
        {"a": 1},
    )
    client.finish_call(call, {"c": 3}, None)

    call_res = client.server.calls_query(
        CallsQueryReq(
            project_id=client._project_id(),
        )
    )
    calls = call_res.calls

    assert len(calls) == 1
    call = calls[0]
    assert (
        call.op_name
        == "weave:///shawn/test-project/op/anonymous_op:MhzyATsFCgR3S91607RSLd2JrqA8Esk2F6hjKfwtwA0"
    )
    assert call.inputs == {"a": 1}
    assert call.output == {"c": 3}
    assert call.exception is None
