import typing

import pytest

from ..api import use
from .. import graph
from .. import weave_types as types
from .. import async_demo
from .. import compile


def test_automatic_await_compile():
    twelve = async_demo.slowmult(3, 4, 0.01)
    twenty_four = async_demo.slowmult(2, twelve, 0.01)
    result = compile.compile([twenty_four])
    assert str(result[0]) == "2.slowmult(slowmult(3, 4, 0.01).await(), 0.01)"


@pytest.mark.parametrize(
    "nodes_with_expected_values",
    [
        # Simple graph with no modification needed
        [
            (
                3,
                graph.OutputNode(
                    types.Number(),
                    "add",
                    {
                        "lhs": graph.ConstNode(types.Number(), 1),
                        "rhs": graph.ConstNode(types.Number(), 2),
                    },
                ),
            )
        ],
        # Single Replacement Needed
        [
            (
                [3, 4, 5],
                graph.OutputNode(
                    types.Number(),
                    "add",
                    {
                        "lhs": graph.ConstNode(types.List(types.Number()), [1, 2, 3]),
                        "rhs": graph.ConstNode(types.Number(), 2),
                    },
                ),
            )
        ],
        # Nested Replacement Needed
        [
            (
                [13, 14, 15],
                graph.OutputNode(
                    types.Number(),
                    "add",
                    {
                        "lhs": graph.OutputNode(
                            types.Number(),
                            "add",
                            {
                                "lhs": graph.ConstNode(
                                    types.List(types.Number()), [1, 2, 3]
                                ),
                                "rhs": graph.ConstNode(types.Number(), 2),
                            },
                        ),
                        "rhs": graph.ConstNode(types.Number(), 10),
                    },
                ),
            )
        ],
        # Nested Replacement Through Valid Node
        [
            (
                [13, 14, 15],
                graph.OutputNode(
                    types.Number(),
                    "add",
                    {
                        "lhs": graph.OutputNode(
                            types.Number(),
                            "index",
                            {
                                "arr": graph.OutputNode(
                                    types.List(types.Number()),
                                    "list",
                                    {
                                        "0": graph.OutputNode(
                                            types.Number(),
                                            "add",
                                            {
                                                "lhs": graph.ConstNode(
                                                    types.List(types.Number()),
                                                    [1, 2, 3],
                                                ),
                                                "rhs": graph.ConstNode(
                                                    types.Number(), 2
                                                ),
                                            },
                                        ),
                                    },
                                ),
                                "index": graph.ConstNode(types.Number(), 0),
                            },
                        ),
                        "rhs": graph.ConstNode(types.Number(), 10),
                    },
                ),
            )
        ],
    ],
)
def test_executing_js_graphs(nodes_with_expected_values):
    nodes = [node for exp_val, node in nodes_with_expected_values]
    exp_vals = [exp_val for exp_val, node in nodes_with_expected_values]
    assert use(nodes) == exp_vals


def test_executing_js_multi_root():
    node = graph.OutputNode(
        types.Number(),
        "add",
        {
            "lhs": graph.ConstNode(
                types.List(types.Number()),
                [1, 2, 3],
            ),
            "rhs": graph.ConstNode(types.Number(), 2),
        },
    )
    node2 = graph.OutputNode(
        types.Number(),
        "add",
        {
            "lhs": node,
            "rhs": graph.ConstNode(types.Number(), 4),
        },
    )
    assert use([node, node2]) == [[3, 4, 5], [7, 8, 9]]
