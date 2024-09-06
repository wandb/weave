import typing

import pytest

import weave
from weave.legacy.weave import context_state as _context
from weave.legacy.weave.weave_internal import make_const_node, make_output_node

_loading_builtins_token = _context.set_loading_built_ins()


@weave.op()
def no_arg_op() -> int:
    return 1


@weave.op()
def int_arg_op(a: int) -> int:
    return a + 1


@weave.op()
def int_args_op(a: int, b: int) -> int:
    return a + b


@weave.op()
def null_consuming_op(a: typing.Optional[int], b: int) -> int:
    if a == None:
        return b * 10
    return a + b  # type: ignore


_context.clear_loading_built_ins(_loading_builtins_token)


def test_basic_nullability():
    b = weave.save(2)
    maybe_int = weave.save([1, None])[0]
    null_int = weave.save([1, None])[1]

    assert weave.use(no_arg_op()) == 1

    assert weave.use(int_arg_op(b)) == 3
    assert weave.use(int_arg_op(maybe_int)) == 2
    assert weave.use(int_arg_op(null_int)) == None

    assert weave.use(int_args_op(b, b)) == 4
    assert weave.use(int_args_op(maybe_int, b)) == 3
    assert weave.use(int_args_op(null_int, b)) == None

    assert weave.use(null_consuming_op(b, b)) == 4
    assert weave.use(null_consuming_op(maybe_int, b)) == 3
    assert weave.use(null_consuming_op(null_int, b)) == 20


def test_basic_nullability_in_mappability():
    b_arr = weave.save([2])
    maybe_int_arr = weave.save(
        weave.legacy.weave.graph.ConstNode(
            weave.types.List(weave.types.optional(weave.types.Int())), [1, None]
        )
    )

    assert weave.use(int_arg_op(b_arr)) == [3]
    assert weave.use(int_arg_op(maybe_int_arr)) == [2, None]

    assert weave.use(int_args_op(b_arr, 2)) == [4]
    assert weave.use(int_args_op(maybe_int_arr, 2)) == [3, None]

    assert weave.use(null_consuming_op(b_arr, 2)) == [4]
    assert weave.use(null_consuming_op(maybe_int_arr, 2)) == [3, 20]


@pytest.mark.parametrize(
    "input_node, expected_type, expected",
    [
        # Base Case
        (
            lambda: weave.save({"a": 42}),
            weave.types.TypedDict({"a": weave.types.Int()}),
            42,
        ),
        # Maybe Case
        (
            lambda: weave.save([{"a": 42}, None])[0],
            weave.types.union(
                weave.types.NoneType(),
                weave.types.TypedDict({"a": weave.types.Int()}),
            ),
            42,
        ),
        # List of Maybe Case
        (
            lambda: weave.save([{"a": 42}, None]),
            weave.types.List(
                weave.types.union(
                    weave.types.NoneType(),
                    weave.types.TypedDict({"a": weave.types.Int()}),
                )
            ),
            [42, None],
        ),
        # Maybe list of Maybe Case
        (
            lambda: weave.save([[{"a": 42}, None], None])[0],
            weave.types.union(
                weave.types.NoneType(),
                weave.types.List(
                    weave.types.union(
                        weave.types.NoneType(),
                        weave.types.TypedDict({"a": weave.types.Int()}),
                    )
                ),
            ),
            [42, None],
        ),
    ],
)
def test_nullability_in_execution(input_node, expected_type, expected):
    input_node = input_node()
    assert input_node.type == expected_type
    # JS Weave0 Pick (noteable incorrect op name)
    js_pick = make_output_node(
        weave.types.Number(),
        "pick",
        {"obj": input_node, "key": make_const_node(weave.types.String(), "a")},
    )
    assert weave.use(js_pick) == expected

    # Ensure that this works at the type level so py dispatch works as well.
    py_pick = input_node.pick("a")
    assert weave.use(py_pick) == expected
