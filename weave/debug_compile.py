from . import graph

from . import debug_types
from . import types


def assign_type_weave0_weave1(w0_type: types.Type, w1_type: types.Type) -> bool:  # type: ignore[empty-body]
    pass


def check_weave0_compile_result(
    weave0_nodes: list[graph.Node], weave1_nodes: list[graph.Node]
) -> None:
    weave0_flat: list[graph.OutputNode] = [
        n for n in graph.all_nodes_full(weave0_nodes) if isinstance(n, graph.OutputNode)
    ]
    weave1_flat: list[graph.OutputNode] = [
        n for n in graph.all_nodes_full(weave1_nodes) if isinstance(n, graph.OutputNode)
    ]
    if len(weave0_flat) != len(weave1_flat):
        print("weave0 and weave1 have different lengths")
        raise ValueError
    for op0, op1 in zip(weave0_flat, weave1_flat):
        if op1.from_op.name != "gqlroot-wbgqlquery":
            if op0.from_op.friendly_name != op1.from_op.friendly_name:
                print("weave0 and weave1 have different op names", op0, op1)
                raise ValueError
            if not op0.type.assign_type(op1.type):
                print(
                    "weave1 type not assignable to weave0 type for op0",
                    op0.from_op.name,
                    op0.type,
                    op1.type,
                )
                print(debug_types.why_not_assignable(op0.type, op1.type))
                raise ValueError
