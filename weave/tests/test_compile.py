import pytest
import wandb

import weave
from weave.weave_internal import define_fn, make_const_node, const
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


def test_optimize_merge_empty_dict():
    non_empty_dict = weave.ops.dict_(a=5, b=2)
    assert (
        compile.compile_simple_optimizations(
            [weave.ops.TypedDict.merge(non_empty_dict, weave.ops.dict_())]
        )[0].to_json()
        == non_empty_dict.to_json()
    )
    assert (
        compile.compile_simple_optimizations(
            [weave.ops.TypedDict.merge(weave.ops.dict_(), non_empty_dict)]
        )[0].to_json()
        == non_empty_dict.to_json()
    )
    non_simplified_merge = weave.ops.TypedDict.merge(
        weave.ops.dict_(j=3), non_empty_dict
    )
    assert (
        compile.compile_simple_optimizations([non_simplified_merge])[0].to_json()
        == non_simplified_merge.to_json()
    )


def count_nodes(node: graph.Node) -> int:
    counter = 0

    def inc(n: graph.Node):
        nonlocal counter
        counter += 1

    weave.graph.map_nodes_full([node], inc)
    return counter


def test_compile_lambda_uniqueness():
    list_node_1 = weave.ops.make_list(a=make_const_node(weave.types.Number(), 1))
    list_node_2 = weave.ops.make_list(a=make_const_node(weave.types.Number(), 2))
    fn_node = define_fn({"row": weave.types.Number()}, lambda row: row + 1)
    mapped_1 = list_node_1.map(fn_node)
    mapped_2 = list_node_2.map(fn_node)
    combined = weave.ops.make_list(a=mapped_1, b=mapped_2)
    concatted = combined.concat()

    # list node contains 2 nodes (const, list), x 2 = 4
    # fn node contains 3 nodes (row, add, const) + the fn node itself, x1 = 4
    # map node contains 1 node, x2 = 2
    # combined node contains 1 node, x1 = 1
    # concat node contains 1 node, x1 = 1
    # total = 12
    assert count_nodes(concatted) == 12

    # However, after lambda compilation, we should get
    # 3 more nodes (new row, add, and fn), creating
    # a total of 15 nodes
    compiled = compile.compile([concatted])[0]
    assert count_nodes(compiled) == 15


# We actually don't want this to work because it would require
# mutating a static lambda function!
# def test_compile_through_execution(user_by_api_key_in_env):
#     run = wandb.init(project="project_exists")
#     for i in range(10):
#         run.log({"val": i, "cat": i % 2})
#     run.finish()

#     """
#     This test demonstrates successful execution when there is an explicit
#     const function instead of a direct node (resulting in an intermediate execution op)
#     """
#     history_node = weave.ops.project(run.entity, run.project).run(run.id).history2()
#     pick = const(history_node).pick("val")
#     res = weave.use(pick)
#     assert res.to_pylist_notags() == list(range(10))


def test_compile_through_function_call(user_by_api_key_in_env):
    run = wandb.init(project="project_exists")
    for i in range(10):
        run.log({"val": i, "cat": i % 2})
    run.finish()

    """
    This test demonstrates successful execution when there is an explicit
    function-__call__ in the graph)
    """
    fn_node = define_fn(
        {"entity_name": types.String()},
        lambda entity_name: (
            weave.ops.project(entity_name, run.project).run(run.id).history2()
        ),
    )
    called_node = fn_node(run.entity)
    pick = called_node.pick("val")
    res = weave.use(pick)
    assert res.to_pylist_notags() == list(range(10))
