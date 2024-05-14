import pytest

from weave.trace.vals import TraceObject
import weave


def test_traceobject_properties():
    class A:
        @property
        def x(self):
            return 1

    to = TraceObject(A(), None, None, None)
    assert to.x == 1


def test_traceobject_access_after_init_termination(client):
    my_obj = None

    class MyObj(weave.Object):
        val: int

    @weave.op()
    def my_op(obj: MyObj) -> None:
        nonlocal my_obj
        my_obj = obj

    my_op(MyObj(val=1))

    assert my_obj.val == 1

    # Here we explicitly close the client in order to
    # simulate a situation where the client is closed
    # but a reference to a trace object still exists.
    from weave import context_state

    context_state._graph_client.set(None)

    assert my_obj.val == 1
