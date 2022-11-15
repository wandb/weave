import typing

from .. import graph_debug
from .. import graph
from .. import decorator_op


class RowType(typing.TypedDict):
    a: int
    b: int
    c: int


@decorator_op.op()
def _test_cn_op1() -> list[int]:
    return [1, 2, 3]


@decorator_op.op()
def _test_cn_op2(v: int, addend: int) -> RowType:
    return {"a": v, "b": v + addend, "c": v + addend * 2}


def test_combine_nodes():
    common_node = _test_cn_op1().map(lambda x: _test_cn_op2(x, 1))
    n1 = common_node[0]["a"]
    n2 = common_node[0]["b"]
    n3 = common_node[0]["c"]
    n4 = common_node[1]["a"]
    n5 = common_node[1]["b"]

    result = graph_debug.combine_common_nodes([n1, n2, n3, n4, n5])
    assert len(result) == 1
    assert (
        graph.node_expr_str(result[0])
        == "_test_cn_op1().map(_test_cn_op2(row, 1))[EACH[0, 1]][EACH['a', 'b', 'c']]"
    )
