from . import api as weave
from . import lazy
from . import graph
from . import types
from . import weave_internal


@weave.op(
    name="test_op-op_simple",
    input_type={"a": types.Int(), "b": types.Int()},
    output_type=types.String(),
)
def op_simple(a, b):
    return (a, b)


def test_op_simple():
    x = op_simple(3, 4)
    assert str(x) == "op_simple(3, 4)"
    assert graph.nodes_equal(
        x,
        graph.OutputNode(
            types.String(),
            "test_op-op_simple",
            {
                "a": weave_internal.make_const_node(types.Int(), 3),
                "b": weave_internal.make_const_node(types.Int(), 4),
            },
        ),
    )
    assert weave.use(x) == (3, 4)


@weave.op(
    name="test_op-op_kwargs",
    # TODO: how to declare input type properly? Not like this! Should match the
    # way Python parameter lists can be typed annotated.
    input_type=types.Dict(types.String(), types.Int),
    output_type=types.String(),
)
def op_kwargs(**kwargs):
    return kwargs


def test_op_kwargs():
    x = op_kwargs(a=1, b=2)
    # TODO: should show calling convention, must include keys or we lose information.
    assert str(x) == "op_kwargs(1, 2)"

    # This is correct, we can always store keyword args in the call.
    # This should be called an op_call instead of Op
    assert graph.nodes_equal(
        x,
        graph.OutputNode(
            types.String(),
            "test_op-op_kwargs",
            {
                "a": weave_internal.make_const_node(types.Int(), 1),
                "b": weave_internal.make_const_node(types.Int(), 2),
            },
        ),
    )
    assert weave.use(x) == {"a": 1, "b": 2}
