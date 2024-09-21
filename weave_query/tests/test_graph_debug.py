import typing

from weave.legacy.weave import decorator_op, graph, graph_debug


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


def test_to_assignment_form():
    common_node = _test_cn_op1().map(lambda x: _test_cn_op2(x, 1))
    n1 = common_node[0]["a"]
    n2 = common_node[0]["b"]
    n3 = common_node[0]["c"]
    n4 = common_node[1]["a"]
    n5 = common_node[1]["b"]

    result = graph_debug.to_assignment_form([n1, n2, n3, n4, n5])
    print(graph_debug.assignments_string(result))
    assert (
        graph_debug.assignments_string(result)
        == """var0 = op-_test_cn_op1()
  .map(  op-_test_cn_op2(row, 1)) 
var1 = list-__getitem__(var0, 1)
  .typedDict-pick(b) 
var2 = list-__getitem__(var0, 1)
  .typedDict-pick(a) 
var3 = list-__getitem__(var0, 0)
  .typedDict-pick(c) 
var4 = list-__getitem__(var0, 0)
  .typedDict-pick(b) 
var5 = list-__getitem__(var0, 0)
  .typedDict-pick(a) """  # noqa: W291
    )
