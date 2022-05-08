from . import api as weave
from . import weave_types as types


def test_function_op_name():
    @weave.op()
    def my_op(a: int, b: int) -> int:
        return a + b

    assert my_op.name == "op-my_op"


def test_method_op_name():
    class MyObjType(types.Type):
        name = "test-decorators-my-obj"

    @weave.weave_class(weave_type=MyObjType)
    class MyObj:
        @weave.op()
        def my_op(self: int, b: int) -> int:
            return self + b

    assert MyObj.my_op.name == "test-decorators-my-obj-my_op"
