import pytest

import weave
from weave.trace_server import trace_server_interface as tsi

# This file tests the different argument variations that can be passed to an op.
#
#
# There are 24 (2 * 2 * 3 * 2) distinct arg shapes, each with a number of variants
#
#                        Astrisk in the table means that the argument is named
#                        we use `*` to indicate the start of keyword-only arguments
#                        rather than using default values ---\
#                                                            |
#                                                            |
# | Example Stub                    | PosArg  | VarArg   | KwArg   | VarKwArg | Variants |
# |---------------------------------|---------|----------|---------|----------|----------|
# | fn()                            |   NO    |    NO    |  NO     |   NO     |    1     |
# | fn(**kwargs)                    |   NO    |    NO    |  NO     |   YES    |    2     |
# | fn(y=0)                         |   NO    |    NO    |  YES    |   NO     |    2     |
# | fn(*, y)                        |   NO    |    NO    |  YES*   |   NO     |    1     |
# | fn(y=0, **kwargs)               |   NO    |    NO    |  YES    |   YES    |    4 + 2 |
# | fn(*, y, **kwargs)              |   NO    |    NO    |  YES*   |   YES    |    2     |
# | fn(*args)                       |   NO    |    YES   |  NO     |   NO     |    2     |
# | fn(*args, **kwargs)             |   NO    |    YES   |  NO     |   YES    |    4     |
# | fn(*args, y=0)                  |   NO    |    YES   |  YES    |   NO     |    4     |
# | fn(*args, y)                    |   NO    |    YES   |  YES*   |   NO     |    2     |
# | fn(*args, y=0, **kwargs)        |   NO    |    YES   |  YES    |   YES    |    8     |
# | fn(*args, y, **kwargs)          |   NO    |    YES   |  YES*   |   YES    |    4     |
# | fn(x)                           |   YES   |    NO    |  NO     |   NO     |    2     |
# | fn(x, **kwargs)                 |   YES   |    NO    |  NO     |   YES    |    4     |
# | fn(x, y=0)                      |   YES   |    NO    |  YES    |   NO     |    4 + 1 |
# | fn(x, *, y)                     |   YES   |    NO    |  YES*   |   NO     |    2     |
# | fn(x, y=0, **kwargs)            |   YES   |    NO    |  YES    |   YES    |    8     |
# | fn(x, *, y, **kwargs)           |   YES   |    NO    |  YES*   |   YES    |    4     |
# | fn(x, *args)                    |   YES   |    YES   |  NO     |   NO     |    4 - 1 |
# | fn(x, *args, **kwargs)          |   YES   |    YES   |  NO     |   YES    |    8 - 2 |
# | fn(x, *args, y=0)               |   YES   |    YES   |  YES    |   NO     |    8 - 2 |
# | fn(x, *args, y)                 |   YES   |    YES   |  YES*   |   NO     |    4 - 1 |
# | fn(x, *args, y=0, **kwargs)     |   YES   |    YES   |  YES    |   YES    |    16 - 4|
# | fn(x, *args, y, **kwargs)       |   YES   |    YES   |  YES*   |   YES    |    8 - 2 |
#
# Within each stub, we will have the following variants:
# * PosArg: If YES, 2x: both with and without keyword
# * VarArg: If YES, 2x: both with and without values
# * KwArg:
#           If YES, 2x: both with and without values.
#           If YES*, 1x
# * VarKwArg: If YES, 2x: both with and without values
#
# Some stubs have a few patterns added or removed to account for python's rules. The +/- indicates the number of patterns
# added or removed.


@pytest.mark.parametrize(
    ("fn", "arg_variations"),
    [
        # | fn()                            |   NO    |    NO    |  NO     |   NO     |    1     |
        (
            (lambda: {}),
            [
                ((), {}),
            ],
        ),
        # | fn(**kwargs)                    |   NO    |    NO    |  NO     |   YES    |    2     |
        (
            (lambda **kwargs: {"kwargs": kwargs}),
            [
                ((), {}),
                ((), {"a": 1}),
            ],
        ),
        # | fn(y=0)                         |   NO    |    NO    |  YES    |   NO     |    2     |
        (
            (lambda y=0: {"y": y}),
            [
                ((), {}),
                ((), {"y": 1}),
            ],
        ),
        # | fn(*, y)                        |   NO    |    NO    |  YES*   |   NO     |    1     |
        (
            (lambda *, y=0: {"y": y}),
            [
                ((), {"y": 1}),
            ],
        ),
        # | fn(y=0, **kwargs)               |   NO    |    NO    |  YES    |   YES    |    4 + 2 |
        (
            (lambda y=0, **kwargs: {"y": y, "kwargs": kwargs}),
            [
                ((), {}),
                ((1,), {}),  # Extra pattern possible with this combination
                ((), {"y": 1}),
                ((), {"a": 1}),
                ((1,), {"a": 2}),  # Extra pattern possible with this combination
                ((), {"y": 1, "a": 2}),
            ],
        ),
        # | fn(*, y, **kwargs)              |   NO    |    NO    |  YES*   |   YES    |    2     |
        (
            (lambda *, y, **kwargs: {"y": y, "kwargs": kwargs}),
            [
                ((), {"y": 1}),
                ((), {"y": 1, "a": 2}),
            ],
        ),
        # | fn(*args)                       |   NO    |    YES   |  NO     |   NO     |    2     |
        (
            (lambda *args: {"args": list(args)}),
            [
                ((), {}),
                ((1,), {}),
            ],
        ),
        # | fn(*args, **kwargs)             |   NO    |    YES   |  NO     |   YES    |    4     |
        (
            (lambda *args, **kwargs: {"args": list(args), "kwargs": kwargs}),
            [
                ((), {}),
                ((1,), {}),
                ((), {"a": 1}),
                ((1,), {"a": 2}),
            ],
        ),
        # | fn(*args, y=0)                  |   NO    |    YES   |  YES    |   NO     |    4     |
        (
            (lambda *args, y=0: {"args": list(args), "y": y}),
            [
                ((), {}),
                ((1,), {}),
                ((), {"y": 1}),
                ((1,), {"y": 2}),
            ],
        ),
        # | fn(*args, y)                    |   NO    |    YES   |  YES*   |   NO     |    2     |
        (
            (lambda *args, y: {"args": list(args), "y": y}),
            [
                ((), {"y": 1}),
                ((1,), {"y": 2}),
            ],
        ),
        # | fn(*args, y=0, **kwargs)        |   NO    |    YES   |  YES    |   YES    |    8     |
        (
            (
                lambda *args, y=0, **kwargs: {
                    "args": list(args),
                    "y": y,
                    "kwargs": kwargs,
                }
            ),
            [
                ((), {}),
                ((1,), {}),
                ((), {"y": 1}),
                ((), {"a": 1}),
                ((1,), {"y": 2}),
                ((), {"y": 1, "a": 2}),
                ((1,), {"a": 2}),
                ((1,), {"y": 2, "a": 2}),
            ],
        ),
        # | fn(*args, y, **kwargs)          |   NO    |    YES   |  YES*   |   YES    |    4     |
        (
            (
                lambda *args, y, **kwargs: {
                    "args": list(args),
                    "y": y,
                    "kwargs": kwargs,
                }
            ),
            [
                ((), {"y": 1}),
                ((1,), {"y": 2}),
                ((), {"y": 1, "a": 2}),
                ((1,), {"y": 2, "a": 3}),
            ],
        ),
        # | fn(x)                           |   YES   |    NO    |  NO     |   NO     |    2     |
        (
            (lambda x: {"x": x}),
            [
                ((), {"x": 1}),
                ((1,), {}),
            ],
        ),
        # | fn(x, **kwargs)                 |   YES   |    NO    |  NO     |   YES    |    4     |
        (
            (lambda x, **kwargs: {"x": x, "kwargs": kwargs}),
            [
                ((), {"x": 1}),
                ((1,), {}),
                ((), {"x": 1, "a": 2}),
                ((1,), {"a": 2}),
            ],
        ),
        # | fn(x, y=0)                      |   YES   |    NO    |  YES    |   NO     |    4 + 1 |
        (
            (lambda x, y=0: {"x": x, "y": y}),
            [
                ((), {"x": 1}),
                ((1,), {}),
                ((1, 2), {}),  # Extra pattern possible with this combination
                ((), {"x": 1, "y": 2}),
                ((1,), {"y": 2}),
            ],
        ),
        # | fn(x, *, y)                     |   YES   |    NO    |  YES*   |   NO     |    2     |
        (
            (lambda x, *, y: {"x": x, "y": y}),
            [
                ((), {"x": 1, "y": 2}),
                ((1,), {"y": 2}),
            ],
        ),
        # | fn(x, y=0, **kwargs)            |   YES   |    NO    |  YES    |   YES    |    8     |
        (
            (lambda x, y=0, **kwargs: {"x": x, "y": y, "kwargs": kwargs}),
            [
                ((), {"x": 1}),
                ((1,), {}),
                ((), {"x": 1, "y": 2}),
                ((1,), {"y": 2}),
                ((), {"x": 1, "a": 2}),
                ((1,), {"a": 2}),
                ((), {"x": 1, "y": 2, "a": 3}),
                ((1,), {"y": 2, "a": 3}),
            ],
        ),
        # | fn(x, *, y, **kwargs)           |   YES   |    NO    |  YES*   |   YES    |    4     |
        (
            (lambda x, *, y, **kwargs: {"x": x, "y": y, "kwargs": kwargs}),
            [
                ((), {"x": 1, "y": 2}),
                ((1,), {"y": 2}),
                ((), {"x": 1, "y": 2, "a": 3}),
                ((1,), {"y": 2, "a": 3}),
            ],
        ),
        # | fn(x, *args)                    |   YES   |    YES   |  NO     |   NO     |    4 - 1 |
        (
            (lambda x, *args: {"x": x, "args": list(args)}),
            [
                ((), {"x": 1}),
                ((1,), {}),
                # ((1,), {"x": 2}), # Invalid
                (
                    (
                        1,
                        2,
                    ),
                    {},
                ),
            ],
        ),
        # | fn(x, *args, **kwargs)          |   YES   |    YES   |  NO     |   YES    |    8 - 2 |
        (
            (lambda x, *args, **kwargs: {"x": x, "args": list(args), "kwargs": kwargs}),
            [
                ((), {"x": 1}),
                ((1,), {}),
                # ((1,), {"x": 2}), # Invalid
                (
                    (
                        1,
                        2,
                    ),
                    {},
                ),
                ((), {"x": 1, "a": 2}),
                ((1,), {"a": 2}),
                # ((1,), {"x": 2, "a": 3}), # Invalid
                ((1, 2), {"a": 3}),
            ],
        ),
        # | fn(x, *args, y=0)               |   YES   |    YES   |  YES    |   NO     |    8 - 2 |
        (
            (lambda x, *args, y=0: {"x": x, "args": list(args), "y": y}),
            [
                ((), {"x": 1}),
                ((1,), {}),
                # ((1,), {"x": 2}), # Invalid
                (
                    (
                        1,
                        2,
                    ),
                    {},
                ),
                ((), {"x": 1, "y": 2}),
                ((1,), {"y": 2}),
                # ((1,), {"x": 2, "y": 3}), # Invalid
                (
                    (
                        1,
                        2,
                    ),
                    {"y": 3},
                ),
            ],
        ),
        # | fn(x, *args, y)                 |   YES   |    YES   |  YES*   |   NO     |    4 - 1 |
        (
            (lambda x, *args, y: {"x": x, "args": list(args), "y": y}),
            [
                ((), {"x": 1, "y": 2}),
                ((1,), {"y": 2}),
                # ((1,), {"x": 2, "y": 3}), # Invalid
                (
                    (
                        1,
                        2,
                    ),
                    {"y": 3},
                ),
            ],
        ),
        # | fn(x, *args, y=0, **kwargs)     |   YES   |    YES   |  YES    |   YES    |    16 - 4|
        (
            (
                lambda x, *args, y=0, **kwargs: {
                    "x": x,
                    "args": list(args),
                    "y": y,
                    "kwargs": kwargs,
                }
            ),
            [
                ((), {"x": 1}),
                ((1,), {}),
                # ((1,), {"x": 2}), # Invalid
                (
                    (
                        1,
                        2,
                    ),
                    {},
                ),
                ((), {"x": 1, "y": 2}),
                ((1,), {"y": 2}),
                # ((1,), {"x": 2, "y": 3}), # Invalid
                (
                    (
                        1,
                        2,
                    ),
                    {"y": 3},
                ),
                ((), {"x": 1, "a": 2}),
                ((1,), {"a": 2}),
                # ((1,), {"x": 2, "a": 3}), # Invalid
                (
                    (
                        1,
                        2,
                    ),
                    {"a": 3},
                ),
                ((), {"x": 1, "y": 2, "a": 3}),
                ((1,), {"y": 2, "a": 3}),
                # ((1,), {"x": 2, "y": 3, "a": 4}), # Invalid
                (
                    (
                        1,
                        2,
                    ),
                    {"y": 3, "a": 4},
                ),
            ],
        ),
        # | fn(x, *args, y, **kwargs)       |   YES   |    YES   |  YES*   |   YES    |    8 - 2|
        (
            (
                lambda x, *args, y, **kwargs: {
                    "x": x,
                    "args": list(args),
                    "y": y,
                    "kwargs": kwargs,
                }
            ),
            [
                ((), {"x": 1, "y": 2}),
                ((1,), {"y": 2}),
                # ((1,), {"x": 2, "y": 3}), # Invalid
                (
                    (
                        1,
                        2,
                    ),
                    {"y": 3},
                ),
                ((), {"x": 1, "y": 2, "a": 3}),
                ((1,), {"y": 2, "a": 3}),
                # ((1,), {"x": 2, "y": 3, "a": 4}), # Invalid
                (
                    (
                        1,
                        2,
                    ),
                    {"y": 3, "a": 4},
                ),
            ],
        ),
    ],
)
def test_general_arg_variations(client, fn, arg_variations):
    """In this test, `fn` is expect to return the value of the inputs."""
    wrapped_fn = weave.op()(fn)
    for ndx, variation in enumerate(arg_variations):
        args = variation[0]
        kwargs = variation[1]

        fn_res = fn(*args, **kwargs)
        wrapped_res = wrapped_fn(*args, **kwargs)

        assert fn_res == wrapped_res

        res = client.server.calls_query(
            tsi.CallsQueryReq(
                project_id=client.project_id,
                filter=tsi.CallsFilter(op_names=[wrapped_fn.ref.uri]),
            )
        )

        assert len(res.calls) == ndx + 1
        assert res.calls[ndx].inputs == fn_res
        assert res.calls[ndx].output == fn_res


# Below are specific tests for each of the 24 stubs
# While the above test is more general and covers all possible variations, the below tests are more specific and
# a bit easier to read and understand (technically, the above test is more comprehensive and should be enough)


def _no_args_op():
    @weave.op
    def my_op() -> int:
        return 1

    return my_op


def _concrete_op():
    @weave.op
    def my_op(val):
        return [val]

    return my_op


def _concrete_splat_op():
    @weave.op
    def my_op(val, *args):
        return [val, args]

    return my_op


def _concrete_splats_op():
    @weave.op
    def my_op(val, *args, **kwargs):
        return [val, args, kwargs]

    return my_op


def _concrete_splat_concrete_op():
    @weave.op
    def my_op(val, *args, a=0):
        return [val, args, a]

    return my_op


def _concrete_splat_concrete_splat_op():
    @weave.op
    def my_op(val, *args, a=0, **kwargs):
        return [val, args, a, kwargs]

    return my_op


@pytest.mark.parametrize(
    ("op_factory", "expected_calls"),
    [
        # | fn()  -> no inputs recorded, output unchecked (matches original)
        (_no_args_op, [((), {}, {}, None)]),
        # | fn(val)
        (_concrete_op, [((1,), {}, {"val": 1}, [1])]),
        # | fn(val, *args)
        (
            _concrete_splat_op,
            [
                ((1,), {}, {"val": 1, "args": []}, [1, []]),
                ((1, 2, 3), {}, {"val": 1, "args": [2, 3]}, [1, [2, 3]]),
            ],
        ),
        # | fn(val, *args, **kwargs)
        (
            _concrete_splats_op,
            [
                ((1,), {}, {"val": 1, "args": [], "kwargs": {}}, [1, [], {}]),
                (
                    (1, 2, 3),
                    {},
                    {"val": 1, "args": [2, 3], "kwargs": {}},
                    [1, [2, 3], {}],
                ),
                (
                    (1,),
                    {"a": 2, "b": 3},
                    {"val": 1, "args": [], "kwargs": {"a": 2, "b": 3}},
                    [1, [], {"a": 2, "b": 3}],
                ),
                (
                    (1, 2, 3),
                    {"a": 4, "b": 5},
                    {"val": 1, "args": [2, 3], "kwargs": {"a": 4, "b": 5}},
                    [1, [2, 3], {"a": 4, "b": 5}],
                ),
            ],
        ),
        # | fn(val, *args, a=0)
        (
            _concrete_splat_concrete_op,
            [
                ((1,), {}, {"val": 1, "args": [], "a": 0}, [1, [], 0]),
                ((1,), {"a": 2}, {"val": 1, "args": [], "a": 2}, [1, [], 2]),
                (
                    (1, 2, 3),
                    {"a": 4},
                    {"val": 1, "args": [2, 3], "a": 4},
                    [1, [2, 3], 4],
                ),
            ],
        ),
        # | fn(val, *args, a=0, **kwargs)
        (
            _concrete_splat_concrete_splat_op,
            [
                (
                    (1,),
                    {},
                    {"val": 1, "args": [], "a": 0, "kwargs": {}},
                    [1, [], 0, {}],
                ),
                (
                    (1,),
                    {"a": 2},
                    {"val": 1, "args": [], "a": 2, "kwargs": {}},
                    [1, [], 2, {}],
                ),
                (
                    (1, 2, 3),
                    {"a": 4},
                    {"val": 1, "args": [2, 3], "a": 4, "kwargs": {}},
                    [1, [2, 3], 4, {}],
                ),
                (
                    (1, 2, 3),
                    {"a": 4, "b": 5},
                    {"val": 1, "args": [2, 3], "a": 4, "kwargs": {"b": 5}},
                    [1, [2, 3], 4, {"b": 5}],
                ),
            ],
        ),
    ],
    ids=[
        "no-args",
        "concrete",
        "concrete-splat",
        "concrete-splats",
        "concrete-splat-concrete",
        "concrete-splat-concrete-splat",
    ],
)
def test_specific_arg_forms(client, op_factory, expected_calls):
    """Concrete per-stub coverage: each call's recorded inputs/output by position.

    The general parametrized test above is more comprehensive; these are the
    individually-readable per-stub forms.
    """
    my_op = op_factory()
    for call_args, call_kwargs, _, _ in expected_calls:
        my_op(*call_args, **call_kwargs)

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client.project_id))

    for ndx, (_, _, expected_inputs, expected_output) in enumerate(expected_calls):
        assert res.calls[ndx].op_name == my_op.ref.uri
        assert res.calls[ndx].inputs == expected_inputs
        if expected_output is not None:
            assert res.calls[ndx].output == expected_output
