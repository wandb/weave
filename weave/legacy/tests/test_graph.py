import weave
from weave.legacy.weave import graph, weave_internal
from weave.legacy.weave import weave_types as types


def test_map_dag_produces_same_len():
    #         3
    #          \
    #   (a) -> (b)
    #     \      \
    # 4 -> (c) -> (d)

    a = weave_internal.make_var_node(types.Int(), "a")
    b = a + 3
    c = a + 4
    d = b + c

    assert id(d.from_op.inputs["lhs"].from_op.inputs["lhs"]) == id(
        d.from_op.inputs["rhs"].from_op.inputs["lhs"]
    )

    assert graph.count(d) == 6

    def replace_a(node: graph.Node) -> graph.Node:
        if isinstance(node, graph.VarNode):
            return weave_internal.make_var_node(types.Int(), "b")
        return node

    mapped_d = graph.map_nodes_top_level([d], replace_a)[0]
    assert id(mapped_d.from_op.inputs["lhs"].from_op.inputs["lhs"]) == id(
        mapped_d.from_op.inputs["rhs"].from_op.inputs["lhs"]
    )
    assert graph.count(mapped_d) == 6


def test_map_nodes_toplevel_doesnt_walk_lambdas():
    l = weave.save([1, 2, 3])
    node = l.map(lambda x: x + 1)
    node_count = {"count": 0}

    def _map_fn(node):
        node_count["count"] += 1

    graph.map_nodes_top_level([node], _map_fn)[0]
    assert node_count["count"] == 4


def test_map_nodes_full_walks_lambdas():
    l = weave.save([1, 2, 3])
    node = l.map(lambda x: x + 1)
    node_count = {"count": 0}

    def _map_fn(node):
        node_count["count"] += 1

    graph.map_nodes_full([node], _map_fn)[0]
    assert node_count["count"] == 7


def test_map_nodes_full_replaces_in_lambda():
    l = weave.save([1, 2, 3])
    node = l.map(lambda x: x + 1)
    assert weave.use(node) == [2, 3, 4]

    def _map_fn(node):
        if isinstance(node, graph.OutputNode) and node.from_op.name == "number-add":
            return graph.OutputNode(node.type, "number-mult", node.from_op.inputs)

    result = graph.map_nodes_full([node], _map_fn)[0]
    assert weave.use(result) == [1, 2, 3]


def test_linearize():
    a = weave_internal.make_var_node(types.Int(), "a")
    dag = ((a + 1) * 2) + 3
    linear = graph.linearize(dag)
    assert len(linear) == 3
    assert linear[0].from_op.name == "number-add"
    assert list(linear[0].from_op.inputs.values())[1].val == 1
    assert linear[1].from_op.name == "number-mult"
    assert list(linear[1].from_op.inputs.values())[1].val == 2
    assert linear[2].from_op.name == "number-add"
    assert list(linear[2].from_op.inputs.values())[1].val == 3


def test_replace_node():
    #    2      3
    #     \      \
    # 1 -> (a) -> (b)
    #        \      \
    #   4 -> (c) -> (d)
    a = weave_internal.make_const_node(types.Int(), 1) + 2
    b = a + 3
    c = a * 4
    d = b + c
    assert weave.use(d) == 18

    def replace_c(node):
        if node is c:
            return c.from_op.inputs["lhs"] / 4

    x = graph.map_nodes_top_level([d], replace_c)[0]
    assert weave.use(x) == 6.75
