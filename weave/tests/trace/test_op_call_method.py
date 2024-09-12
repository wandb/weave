import pytest

import weave
from weave.trace.errors import OpCallError


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
    assert isinstance(call, weave.trace.weave_client.Call)
    assert call.inputs == {"a": 1, "b": 2}
    assert call.output == 3
    assert res2 == 3


def test_op_call_class_with_method(client):
    class Thing(weave.Object):
        x: int

        @weave.op
        def add(self, y: int) -> int:
            return self.x + y

    t = Thing(x=1)
    assert t.add(2) == 3

    res, _ = t.add.call(t, 2)
    assert res == 3

    with pytest.raises(OpCallError, match="missing a required argument"):
        t.add.call(2)  # missing self "t"
