import pytest

from weave.legacy.weave import graph, ops, weave_internal
from weave.legacy.weave import weave_types as types

from ...legacy.weave import weavify
from weave.legacy.tests.util import geom


@pytest.mark.parametrize(
    "name,object,expected",
    [
        ("dict", {"a": 1, "b": 2}, ops.dict_(**{"a": 1, "b": 2})),
        ("int", 1, weave_internal.make_const_node(types.Int(), 1)),
        ("float", 1.0, weave_internal.make_const_node(types.Float(), 1.0)),
        ("string", "a", weave_internal.make_const_node(types.String(), "a")),
        ("bool", True, weave_internal.make_const_node(types.Boolean(), True)),
        (
            "mixed list",
            [1, weave_internal.make_const_node(types.Int(), 2)],
            ops.make_list(**{"0": 1, "1": 2}),
        ),
        (
            "recursive dict",
            {"a": {"b": 1}, "d": 2},
            ops.dict_(**{"a": ops.dict_(**{"b": 1}), "d": 2}),
        ),
        (
            "recursive list",
            [1, [2, 3]],
            ops.make_list(**{"0": 1, "1": ops.make_list(**{"0": 2, "1": 3})}),
        ),
        (
            "recursive mixed",
            {"a": [1, 2], "b": {"c": 3}},
            ops.dict_(
                **{"a": ops.make_list(**{"0": 1, "1": 2}), "b": ops.dict_(**{"c": 3})}
            ),
        ),
        ("none", None, weave_internal.make_const_node(types.NoneType(), None)),
        # decorator_type() constructor generation is disabled.
        # (
        #     "object",
        #     geom.Point2d(1, 2),
        #     geom.Point2d.constructor(x=1, y=2),  # type: ignore
        # ),
        # (
        #     "mixed object",
        #     {"a": geom.Point2d(1, 2)},
        #     ops.dict_(**{"a": geom.Point2d.constructor(x=1, y=2)}),  # type: ignore
        # ),
        # (
        #     "mixed object list",
        #     [
        #         geom.Point2d(1, 2),
        #         geom.Point2d.constructor(  # type: ignore
        #             x=weave_internal.make_const_node(types.Int(), 1),
        #             y=weave_internal.make_const_node(types.Int(), 2),
        #         ),
        #     ],
        #     ops.make_list(
        #         **{
        #             "0": geom.Point2d.constructor(x=1, y=2),  # type: ignore
        #             "1": geom.Point2d.constructor(x=1, y=2),  # type: ignore
        #         }
        #     ),
        # ),
    ],
)
def test_weavify_object(name, object, expected):
    assert graph.nodes_equal(weavify.weavify_object(object), expected)
