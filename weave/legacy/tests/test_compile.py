import pytest
import wandb

import weave
from weave.legacy.weave import async_demo, compile, graph
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.api import use
from weave.legacy.weave.dispatch import RuntimeOutputNode
from weave.legacy.weave.ops_arrow import to_arrow
from weave.legacy.weave.ops_arrow.vectorize import raise_on_python_bailout
from weave.legacy.weave.wandb_interface.wandb_stream_table import StreamTable
from weave.legacy.weave.weave_internal import const, define_fn, make_const_node


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
    non_empty_dict = weave.legacy.weave.ops.dict_(a=5, b=2)
    assert (
        compile.compile_simple_optimizations(
            [weave.legacy.weave.ops.TypedDict.merge(non_empty_dict, weave.legacy.weave.ops.dict_())]
        )[0].to_json()
        == non_empty_dict.to_json()
    )
    assert (
        compile.compile_simple_optimizations(
            [weave.legacy.weave.ops.TypedDict.merge(weave.legacy.weave.ops.dict_(), non_empty_dict)]
        )[0].to_json()
        == non_empty_dict.to_json()
    )
    non_simplified_merge = weave.legacy.weave.ops.TypedDict.merge(
        weave.legacy.weave.ops.dict_(j=3), non_empty_dict
    )
    assert (
        compile.compile_simple_optimizations([non_simplified_merge])[0].to_json()
        == non_simplified_merge.to_json()
    )


def test_compile_lambda_uniqueness():
    list_node_1 = weave.legacy.weave.ops.make_list(a=make_const_node(weave.types.Number(), 1))
    list_node_2 = weave.legacy.weave.ops.make_list(a=make_const_node(weave.types.Number(), 2))
    fn_node = define_fn({"row": weave.types.Number()}, lambda row: row + 1)
    mapped_1 = list_node_1.map(fn_node)
    mapped_2 = list_node_2.map(fn_node)
    combined = weave.legacy.weave.ops.make_list(a=mapped_1, b=mapped_2)
    concatted = combined.concat()

    # list node contains 2 nodes (const, list), x 2 = 4
    # fn node contains 3 nodes (row, add, const) + the fn node itself, x1 = 4
    # map node contains 1 node, x2 = 2
    # combined node contains 1 node, x1 = 1
    # concat node contains 1 node, x1 = 1
    # total = 12
    assert graph.count(concatted) == 12

    # However, after lambda compilation, we should get
    # 3 more nodes (new row, add, and fn), the const 1
    # is not deduped because in one case (inside the lambda function),
    # it is an int and in the other, it is a number
    compiled = compile.compile([concatted])[0]

    assert graph.count(compiled) == 15


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
#     history_node = weave.legacy.weave.ops.project(run.entity, run.project).run(run.id).history2()
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
            weave.legacy.weave.ops.project(entity_name, run.project).run(run.id).history2()
        ),
    )
    called_node = fn_node(run.entity)
    pick = called_node.pick("val")
    res = weave.use(pick)
    assert res.to_pylist_notags() == list(range(10))


def test_compile_list_flatten_to_awl_concat():
    # 4 cases: list of lists, list of awls, awl of lists, awl of awls
    # When the outer list-structure is a list, we want to dispatch to concat, preferably AWL-concat
    # when the outer list-structure is an AWL, we want to dispatch ensure that we use AWL ops
    # list of lists
    list_list_node = weave.legacy.weave.ops.make_list(a=[1], b=[2])
    list_list_node_concat = list_list_node.concat()
    list_list_node_flatten = list_list_node.flatten()
    list_list_node_concat_compiled = compile.compile([list_list_node_concat])[0]
    list_list_node_flatten_compiled = compile.compile([list_list_node_flatten])[0]
    assert list_list_node_concat_compiled.from_op.name == "concat"
    assert list_list_node_flatten_compiled.from_op.name == "flatten"
    # list of awls
    list_awl_node = weave.legacy.weave.ops.make_list(a=to_arrow([1]), b=to_arrow([2]))
    list_awl_node_concat = list_awl_node.concat()
    list_awl_node_flatten = list_awl_node.flatten()
    list_awl_node_concat_compiled = compile.compile([list_awl_node_concat])[0]
    list_awl_node_flatten_compiled = compile.compile([list_awl_node_flatten])[0]
    assert list_awl_node_concat_compiled.from_op.name == "ArrowWeaveList-concat"
    # **THIS IS THE SPECIAL CASE 1**: the flatten operation is transformed into a concat!
    assert list_awl_node_flatten_compiled.from_op.name == "ArrowWeaveList-concat"
    # awl of lists
    awl_list_node = weave.save(to_arrow([[1], [2]]))
    awl_list_node_concat = awl_list_node.concat()
    awl_list_node_flatten = awl_list_node.flatten()
    awl_list_node_concat_compiled = compile.compile([awl_list_node_concat])[0]
    awl_list_node_flatten_compiled = compile.compile([awl_list_node_flatten])[0]
    # **THIS IS THE SPECIAL CASE 2**: the concat operation is transformed into a flatten!
    assert awl_list_node_concat_compiled.from_op.name == "ArrowWeaveList-flatten"
    assert awl_list_node_flatten_compiled.from_op.name == "ArrowWeaveList-flatten"
    # awl of awls
    awl_awl_node = weave.save(to_arrow([to_arrow([1]), to_arrow([2])]))
    awl_awl_node_concat = awl_awl_node.concat()
    awl_awl_node_flatten = awl_awl_node.flatten()
    awl_awl_node_concat_compiled = compile.compile([awl_awl_node_concat])[0]
    awl_awl_node_flatten_compiled = compile.compile([awl_awl_node_flatten])[0]
    assert awl_awl_node_concat_compiled.from_op.name == "ArrowWeaveList-concat"
    assert awl_awl_node_flatten_compiled.from_op.name == "ArrowWeaveList-flatten"

    results = weave.use(
        [
            list_list_node_concat,
            list_list_node_flatten,
            list_awl_node_concat,
            list_awl_node_flatten,
            awl_list_node_concat,
            awl_list_node_flatten,
            awl_awl_node_concat,
            awl_awl_node_flatten,
        ]
    )

    for result in results[:2]:
        assert result == [1, 2]
    for result in results[2:]:
        assert result.to_pylist_notags() == [1, 2]


def test_compile_lambda_on_refineable(user_by_api_key_in_env):
    st = StreamTable(
        "test_table",
        project_name="stream-tables",
        entity_name=user_by_api_key_in_env.username,
        _disable_async_file_stream=True,
    )

    for i in range(10):
        st.log({"num": i, "str": str(i)})

    st.finish()

    rows_node = st.rows()
    rows_node_copy = RuntimeOutputNode(
        types.List(types.TypedDict({})),
        rows_node.from_op.name,
        rows_node.from_op.inputs,
    )
    mapped_node = rows_node_copy.map(lambda row: row["num"] + 1)
    with raise_on_python_bailout():
        val = use(mapped_node)
    assert val.to_pylist_raw() == list(range(1, 11))
