import weave
from weave.trace.weave_client import WeaveClient


def test_weave_log_call(client: WeaveClient):
    call = weave.log_call("test", {"a": 1}, 2)
    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    call = fetched_calls[0]
    assert call.op_name.startswith("weave:///shawn/test-project/op/test:")
    assert call.inputs == {"a": 1}
    assert call.output == 2
