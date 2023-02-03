import json
import copy
import typing

from . import graph
from . import weave_types as types


class _CombinedConstVal:
    """Special value to respresent the combination of multiple values in debug output."""

    def __init__(self, vals: typing.Sequence[typing.Any]):
        self.vals = dict.fromkeys(vals)

    def union(self, other: "_CombinedConstVal") -> "_CombinedConstVal":
        vals = copy.copy(self.vals)
        vals.update(other.vals)
        return _CombinedConstVal(list(vals.keys()))

    def __str__(self) -> str:
        return "EACH[%s]" % ", ".join(v.__repr__() for v in sorted(self.vals))


def _combine_graphs_by_consts(
    node1: graph.Node, node2: graph.Node
) -> typing.Union[graph.Node, None]:
    if node1.type != node2.type:
        return None
    if isinstance(node1, graph.ConstNode) and isinstance(node2, graph.ConstNode):
        if isinstance(node1.type, types.Function) and isinstance(
            node2.type, types.Function
        ):
            combined_fn = _combine_graphs_by_consts(node1.val, node2.val)
            if combined_fn is None:
                return None
            return graph.ConstNode(node1.type, combined_fn)
        if not isinstance(node1.type, types.BasicType):
            return None
        if node1.val == node2.val:
            return node1
        node1_vals = node1.val
        if not isinstance(node1_vals, _CombinedConstVal):
            node1_vals = _CombinedConstVal((node1_vals,))
        node2_vals = node2.val
        if not isinstance(node2_vals, _CombinedConstVal):
            node2_vals = _CombinedConstVal((node2_vals,))
        return graph.ConstNode(node1.type, node1_vals.union(node2_vals))
    elif isinstance(node1, graph.OutputNode) and isinstance(node2, graph.OutputNode):
        new_inputs = {}
        if len(node1.from_op.inputs) != len(node2.from_op.inputs):
            return None
        for (k1, input1), (k2, input2) in zip(
            node1.from_op.inputs.items(), node2.from_op.inputs.items()
        ):
            if k1 != k2:
                return None
            new_input = _combine_graphs_by_consts(input1, input2)
            if new_input is None:
                return None
            new_inputs[k1] = new_input
        return graph.OutputNode(node1.type, node1.from_op.name, new_inputs)
    elif isinstance(node1, graph.VarNode) and isinstance(node2, graph.VarNode):
        if node1.name == node2.name:
            return node1
        return None
    elif isinstance(node1, graph.VoidNode) and isinstance(node2, graph.VoidNode):
        return node1
    return None


ItemType = typing.TypeVar("ItemType")


# TODO: move to general util
def merge(
    items: list[ItemType],
    combine_fn: typing.Callable[[ItemType, ItemType], typing.Union[ItemType, None]],
) -> list[ItemType]:
    """
    Merges items in a list by combining them with combine_fn. If combine_fn
    returns None, then the items are not combined.

    This is an inefficient implementation, its runtime is O(n^2).
    """
    new_items: list[ItemType] = []
    for item in items:
        for i, new_item in enumerate(new_items):
            combined = combine_fn(item, new_item)
            if combined is not None:
                new_items[i] = combined
                break
        else:
            new_items.append(item)
    return new_items


def combine_common_nodes(outputs: list[graph.Node]) -> list[graph.Node]:
    """Simplifies a dag or set of dags by combining similar structures.

    This produces Nodes, but they are no longer executable because we
    replace values with _CombinedConstVal. So the results should
    only be used for debugging/printing.
    """
    # if two graphs differ only by Consts, then combine them.
    return merge(outputs, _combine_graphs_by_consts)


def node_expr_str_full(node: graph.Node) -> str:
    """Prints Node as an expression string, with full op names.

    This function is a copy/modification of of node_expr_str.
    """
    if isinstance(node, graph.OutputNode):
        if node.from_op.name == "gqlroot-wbgqlquery":
            query_hash = "_query_"  # TODO: make a hash from the query for idenity
            return f"{node.from_op.friendly_name}({query_hash})"
        param_names = list(node.from_op.inputs.keys())
        if all(
            [not isinstance(n, graph.OutputNode) for n in node.from_op.inputs.values()]
        ):
            return "%s(%s)" % (
                graph.opuri_full_name(node.from_op.name),
                ", ".join(
                    node_expr_str_full(node.from_op.inputs[n]) for n in param_names
                ),
            )
        if not param_names:
            return "%s()" % graph.opuri_full_name(node.from_op.name)
        return "%s.%s(%s)" % (
            node_expr_str_full(node.from_op.inputs[param_names[0]]),
            graph.opuri_full_name(node.from_op.name),
            ", ".join(
                node_expr_str_full(node.from_op.inputs[n]) for n in param_names[1:]
            ),
        )
    elif isinstance(node, graph.ConstNode):
        if isinstance(node.type, types.Function):
            res = node_expr_str_full(node.val)
            return res
        try:
            return json.dumps(node.val)
        except TypeError:
            # WARNING: This behavior means that sometimes this function
            # produces expressionions that JS can't parse (it happens when
            # we have Python Objects as values that have not yet been serialized)
            # TODO: fix
            return str(node.val)
    elif isinstance(node, graph.VarNode):
        return node.name
    elif isinstance(node, graph.VoidNode):
        return "<void>"
    else:
        return "**PARSE_ERROR**"
