import pytest

import weave
import weave.trace.call
from tests.trace.util import FAKE_NOT_IMPLEMENTED


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_op_call_method(weave_active):
    @weave.op
    def add(a, b):
        return a + b

    # regular call
    res = add(1, 2)
    assert isinstance(res, int)
    assert res == 3

    # call that returns a Call obj
    res2, call = add.call(1, 2)
    assert isinstance(call, weave.trace.call.Call)
    assert call.inputs == {"a": 1, "b": 2}
    assert call.output == 3
    assert res2 == 3
