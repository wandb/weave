import typing

import pytest

from weave.legacy.weave import api as weave
from weave.legacy.weave import context_state, graph, storage, uris, weave_internal
from weave.legacy.weave import context_state as _context_state
from weave.legacy.weave import weave_types as types

from . import test_helpers

_loading_builtins_token = _context_state.set_loading_built_ins()


@weave.op(
    name="test_op-op_simple",
    input_type={"a": types.Int(), "b": types.Int()},
    output_type=types.String(),
)
def op_simple(a, b):
    return str(a) + str(b)


def test_op_simple():
    x = op_simple(3, 4)
    assert str(x) == "op_simple(3, 4)"
    test_helpers.assert_nodes_equal(
        x,
        graph.OutputNode(
            types.String(),
            test_helpers.RegexMatcher(".*test_op-op_simple.*"),
            {
                "a": weave_internal.make_const_node(types.Int(), 3),
                "b": weave_internal.make_const_node(types.Int(), 4),
            },
        ),
    )
    assert weave.use(x) == "34"


@weave.op()
def op_inferredtype(a: int, b: int) -> str:
    return str(a) + str(b)


_context_state.clear_loading_built_ins(_loading_builtins_token)


def test_op_inferred_type():
    assert op_inferredtype.input_type.arg_types == {
        "a": types.Int(),
        "b": types.Int(),
    }
    assert op_inferredtype.concrete_output_type == types.String()


def test_op_incompatible_return_type():
    with pytest.raises(weave.errors.WeaveDefinitionError):
        _t = _context_state.set_loading_built_ins()

        try:

            @weave.op(output_type=types.Int())
            def op_invalid_returntype(a: int, b: int) -> str:
                return str(a) + str(b)

        finally:
            _context_state.clear_loading_built_ins(_t)


def test_op_incompatible_input_arg_type():
    with pytest.raises(weave.errors.WeaveDefinitionError):
        _t = _context_state.set_loading_built_ins()

        try:

            @weave.op(
                input_type={"a": types.String(), "b": types.Int()},
                output_type=types.Int(),
            )
            def op_invalid_input_arg_type(a: int, b: int) -> str:
                return str(a) + str(b)

        finally:
            _context_state.clear_loading_built_ins(_t)


def test_op_too_few_input_arg_type():
    with pytest.raises(weave.errors.WeaveDefinitionError):
        _t = _context_state.set_loading_built_ins()

        try:

            @weave.op(input_type={"a": types.Int()}, output_type=types.Int())
            def op_invalid_too_few(a: int, b: int) -> str:
                return str(a) + str(b)

        finally:
            _context_state.clear_loading_built_ins(_t)


def test_op_too_many_input_arg_type():
    with pytest.raises(weave.errors.WeaveDefinitionError):
        _t = _context_state.set_loading_built_ins()

        try:

            @weave.op(
                input_type={"a": types.Int(), "b": types.Int(), "c": types.Int()},
            )
            def op_invalid_too_many(a: int, b: int) -> str:
                return str(a) + str(b)

        finally:
            _context_state.clear_loading_built_ins(_t)


def test_op_callable_output_type_and_return_type_declared():
    with pytest.raises(weave.errors.WeaveDefinitionError):
        _t = _context_state.set_loading_built_ins()
        try:

            @weave.op(
                input_type={"a": types.Int()}, output_type=lambda a: types.String()
            )
            def op_callable_output_type_and_return_type_declared(a: int) -> str:
                return str(a)

        finally:
            _context_state.clear_loading_built_ins(_t)


def test_op_no_arg_type():
    with pytest.raises(weave.errors.WeaveDefinitionError):
        with context_state.loading_builtins(True):

            @weave.op()
            def op_callable_output_type_and_return_type_declared(a: int):
                return str(a)


class SomeUnknownObj:
    pass


@pytest.mark.skip("We allow Unknown types now")
def test_op_unknown_arg_type():
    with pytest.raises(weave.errors.WeaveDefinitionError):

        @weave.op()
        def op_callable_output_type_and_return_type_declared(a: SomeUnknownObj):
            return str(a)


def test_op_no_return_type():
    with pytest.raises(weave.errors.WeaveDefinitionError):
        with context_state.loading_builtins(True):

            @weave.op(input_type={"a": types.Int()})
            def op_callable_output_type_and_return_type_declared(a: int):
                return str(a)


def test_op_inferred_list_return():
    _t = _context_state.set_loading_built_ins()
    try:

        @weave.op()
        def op_under_test(a: int) -> list[int]:
            return [a, 2 * a, 3 * a]

    finally:
        _context_state.clear_loading_built_ins(_t)

    assert op_under_test.concrete_output_type == types.List(types.Int())


def test_op_inferred_typeddict_return():
    _t = _context_state.set_loading_built_ins()
    try:

        @weave.op()
        def op_test_op_inferred_typeddict_return_op(
            a: int,
        ) -> typing.TypedDict("OpReturn", {"x": int, "y": str}):
            return {"a": 1, "y": "x"}

    finally:
        _context_state.clear_loading_built_ins(_t)

    assert (
        op_test_op_inferred_typeddict_return_op.concrete_output_type
        == types.TypedDict({"x": types.Int(), "y": types.String()})
    )


def test_op_inferred_list_typeddict_return():
    _t = _context_state.set_loading_built_ins()
    try:

        @weave.op()
        def op_inferred_list_typeddict_return(
            a: int,
        ) -> list[typing.TypedDict("OpReturn", {"x": int, "y": str})]:
            return [{"a": 1, "y": "x"}]

    finally:
        _context_state.clear_loading_built_ins(_t)

    assert op_inferred_list_typeddict_return.concrete_output_type == types.List(
        types.TypedDict({"x": types.Int(), "y": types.String()})
    )


def test_op_inferred_dict_return() -> None:
    _t = _context_state.set_loading_built_ins()
    try:

        @weave.op()
        def op_inferred_dict_return(a: int) -> dict[str, list[int]]:
            return {"a": [5]}

    finally:
        _context_state.clear_loading_built_ins(_t)

    assert op_inferred_dict_return.concrete_output_type == types.Dict(
        types.String(), types.List(types.Int())
    )


def test_op_method_inferred_self():
    class SomeWeaveType(types.Type):
        name = "SomeWeaveType"

    _t = _context_state.set_loading_built_ins()
    try:

        @weave.weave_class(weave_type=SomeWeaveType)
        class SomeWeaveObj:
            @weave.op()
            def my_op(self, a: int) -> str:  # type: ignore[empty-body]
                pass

    finally:
        _context_state.clear_loading_built_ins(_t)

    assert SomeWeaveObj.my_op.input_type.arg_types == {
        "self": SomeWeaveType(),
        "a": types.Int(),
    }
    assert SomeWeaveObj.my_op.concrete_output_type == types.String()


def test_op_internal_tracing_enabled(client):
    # This test verifies the behavior of `_tracing_enabled` which
    # is not a user-facing API and is used internally to toggle
    # tracing on and off.
    @weave.op
    def my_op():
        return "hello"

    my_op()  # <-- this call will be traced

    assert len(list(my_op.calls())) == 1

    my_op._tracing_enabled = False

    my_op()  # <-- this call will not be traced

    assert len(list(my_op.calls())) == 1

    my_op._tracing_enabled = True

    my_op()  # <-- this call will be traced

    assert len(list(my_op.calls())) == 2
