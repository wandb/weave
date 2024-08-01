import weave


def test_op_call_method(client):
    @weave.op
    def add(a, b):
        return a + b

    # regular call
    res = add(1, 2)
    assert isinstance(res, int)
    assert res == 3

    # call that returns a Call obj
    res2, call = add.call(1, 2)
    assert isinstance(call, weave.weave_client.Call)
    assert call.inputs == {"a": 1, "b": 2}
    assert call.output == 3
    assert res2 == 3
