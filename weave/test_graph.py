from . import weave_types as types
from . import weave_internal
from . import graph


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

    mapped_d = graph.map_nodes(d, replace_a)
    assert id(mapped_d.from_op.inputs["lhs"].from_op.inputs["lhs"]) == id(
        mapped_d.from_op.inputs["rhs"].from_op.inputs["lhs"]
    )
    assert graph.count(mapped_d) == 6
