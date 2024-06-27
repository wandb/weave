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
    c = add.call(1, 2)
    assert isinstance(c._val, weave.weave_client.Call)
    assert c.inputs == {"a": 1, "b": 2}
    assert c.output == 3
