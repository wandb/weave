import weave
from weave.trace.vals import WeaveObject


def test_weaveobject_properties():
    class A:
        @property
        def x(self):
            return 1

    to = WeaveObject(A(), None, None, None)
    assert to.x == 1


def test_weaveobject_access_after_init_termination(client):
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

    weave.trace.client_context.weave_client.set_weave_client_global(None)

    assert my_obj.val == 1
