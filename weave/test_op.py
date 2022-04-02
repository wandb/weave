import pytest
from . import api as weave
from . import graph
from . import types
from . import weave_internal
from . import test_helpers


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
    test_helpers.assert_nodes_equal(
        x,
        graph.OutputNode(
            types.String(),
            "test_op-op_simple",
            {
                "a": weave_internal.make_const_node(types.Const(types.Int(), 3), 3),
                "b": weave_internal.make_const_node(types.Const(types.Int(), 4), 4),
            },
        ),
    )
    assert weave.use(x) == (3, 4)


@weave.op(
    name="test_op-op_kwargs",
    input_type=weave.OpVarArgs(types.Int()),
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
    test_helpers.assert_nodes_equal(
        x,
        graph.OutputNode(
            types.String(),
            "test_op-op_kwargs",
            {
                "a": weave_internal.make_const_node(types.Const(types.Int(), 1), 1),
                "b": weave_internal.make_const_node(types.Const(types.Int(), 2), 2),
            },
        ),
    )
    assert weave.use(x) == {"a": 1, "b": 2}


@weave.op()
def op_inferredtype(a: int, b: int) -> str:
    return str(a) + str(b)


def test_op_inferred_type():
    assert op_inferredtype.op_def.input_type == {"a": types.Int(), "b": types.Int()}
    assert op_inferredtype.op_def.output_type == types.String()


def test_op_incompatible_return_type():
    with pytest.raises(weave.errors.WeaveDefinitionError):

        @weave.op(output_type=types.Int())
        def op_invalid_returntype(a: int, b: int) -> str:
            return str(a) + str(b)


def test_op_incompatible_input_arg_type():
    with pytest.raises(weave.errors.WeaveDefinitionError):

        @weave.op(
            input_type={"a": types.String(), "b": types.Int()}, output_type=types.Int()
        )
        def op_invalid_input_arg_type(a: int, b: int) -> str:
            return str(a) + str(b)


def test_op_too_few_input_arg_type():
    with pytest.raises(weave.errors.WeaveDefinitionError):

        @weave.op(input_type={"a": types.Int()}, output_type=types.Int())
        def op_invalid_too_few(a: int, b: int) -> str:
            return str(a) + str(b)


def test_op_too_many_input_arg_type():
    with pytest.raises(weave.errors.WeaveDefinitionError):

        @weave.op(
            input_type={"a": types.Int(), "b": types.Int(), "c": types.Int()},
        )
        def op_invalid_too_many(a: int, b: int) -> str:
            return str(a) + str(b)


def test_op_callable_output_type_and_return_type_declared():
    with pytest.raises(weave.errors.WeaveDefinitionError):

        @weave.op(input_type={"a": types.Int()}, output_type=lambda a: types.String())
        def op_callable_output_type_and_return_type_declared(a: int) -> str:
            return str(a)


def test_op_no_arg_type():
    with pytest.raises(weave.errors.WeaveDefinitionError):

        @weave.op()
        def op_callable_output_type_and_return_type_declared(a: int):
            return str(a)


class SomeUnknownObj:
    pass


def test_op_unknown_arg_type():
    with pytest.raises(weave.errors.WeaveDefinitionError):

        @weave.op()
        def op_callable_output_type_and_return_type_declared(a: SomeUnknownObj):
            return str(a)


def test_op_no_return_type():
    with pytest.raises(weave.errors.WeaveDefinitionError):

        @weave.op(input_type={"a": types.Int()})
        def op_callable_output_type_and_return_type_declared(a: int):
            return str(a)
