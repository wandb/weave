import itertools
import textwrap
import typing

from . import graph
from . import forward_graph
from . import weave_types as types


class _CombinedConstVal:
    """Special value to respresent the combination of multiple values in debug output."""

    def __init__(self, vals: typing.Sequence[typing.Any]):
        self.vals = vals

    def __str__(self) -> str:
        s_vals = [v.__repr__() for v in self.vals]
        s_vals_uniq = sorted(dict.fromkeys(s_vals).keys())
        return "EACH[%s]" % ", ".join(s_vals_uniq)


def combine_common_nodes(outputs: list[graph.Node]) -> list[graph.Node]:
    """Simplifies a dag or set of dags by combining similar structures.

    This produces Nodes, but they are no longer executable because we
    replace values with _CombinedConstVal. So the results should
    only be used for debugging/printing.
    """
    fg = forward_graph.ForwardGraph(allow_var_nodes=True)
    fg.add_nodes(outputs)
    new_outputs: list[graph.Node] = []
    next_items = list(fg.roots)
    replacements: dict[graph.Node, graph.OutputNode] = {}
    while next_items:
        forward_node = next_items.pop()
        if not forward_node.input_to:
            # This is a leaf node, so we can't combine it
            new_node = graph.OutputNode(
                forward_node.node.type,
                forward_node.node.from_op.name,
                {
                    k: replacements.get(v, v)
                    for k, v in forward_node.node.from_op.inputs.items()
                },
            )
            new_outputs.append(new_node)
            continue
        input_to = forward_node.input_to
        combinable_forward_nodes: set[forward_graph.ForwardNode] = set()

        # Find input forward nodes that are mergeable
        for fn in input_to:
            inputs = list(fn.node.from_op.inputs.values())
            if all(
                replacements.get(i, i) is forward_node.node
                or (
                    isinstance(i, graph.ConstNode)
                    and not isinstance(i.val, graph.OutputNode)
                )
                for i in inputs
            ):
                combinable_forward_nodes.add(fn)
            else:
                if fn not in next_items:
                    next_items.append(fn)

        # Group by op and merge
        name_key = (
            lambda n: n.node.from_op.name
            + "-"
            + "".join(
                "1" if isinstance(i, graph.ConstNode) else "0"
                for i in n.node.from_op.inputs.values()
            )
        )
        op_groups = itertools.groupby(
            sorted(combinable_forward_nodes, key=name_key), key=name_key
        )
        for k, group_nodes_iter in op_groups:
            group_nodes = list(group_nodes_iter)
            node0 = group_nodes[0]
            node0_inputs = list(node0.node.from_op.inputs.items())
            node_inputs: dict[str, forward_graph.ExecutableNode]
            if len(group_nodes) == 1:
                node_inputs = node0.node.from_op.inputs
            else:
                node_inputs = {}
                for input_name, input_node in node0_inputs:
                    if replacements.get(input_node, input_node) is forward_node.node:
                        node_inputs[input_name] = replacements.get(
                            input_node, input_node
                        )
                    else:
                        node_inputs[input_name] = graph.ConstNode(
                            input_node.type,
                            _CombinedConstVal(
                                [
                                    op.node.from_op.inputs[input_name].val
                                    for op in group_nodes
                                ]
                            ),
                        )
            new_inner_input_to: dict[
                forward_graph.ForwardNode, typing.Literal[True]
            ] = {}
            for o in group_nodes:
                new_inner_input_to.update(o.input_to)
            new_node = graph.OutputNode(
                node0.node.type, node0.node.from_op.name, node_inputs
            )
            for o in group_nodes:
                replacements[o.node] = new_node
            new_forward_node = forward_graph.ForwardNode(new_node)
            new_forward_node.input_to = new_inner_input_to
            if new_forward_node not in next_items:
                next_items.append(new_forward_node)

    return new_outputs


def node_expr_str_full(node: graph.Node) -> str:
    """Prints Node as an expression string, with full op names.

    This function is a copy/modification of of node_expr_str.
    """

    from . import partial_object

    if isinstance(node, graph.OutputNode):
        if node.from_op.name == "dict":
            return "dict(%s)" % ", ".join(
                "%s= %s" % (k, node_expr_str_full(v))
                for k, v in node.from_op.inputs.items()
            )
        elif node.from_op.name == "ArrowWeaveList-vectorizedDict":
            return "ArrowWeaveList-vectorizedDict(%s)" % ", ".join(
                "%s= %s" % (k, node_expr_str_full(v))
                for k, v in node.from_op.inputs.items()
            )
        if node.from_op.name == "gqlroot-wbgqlquery":
            query_hash = "_query_"  # TODO: make a hash from the query for idenity
            return f"{node.from_op.friendly_name}({query_hash})"
        elif node.from_op.name == "gqlroot-querytoobj":
            param_names = list(node.from_op.inputs.keys())
            const = node.from_op.inputs[param_names[2]]
            try:
                assert isinstance(const, graph.ConstNode)
                narrow_type = const.val
                assert isinstance(narrow_type, partial_object.PartialObjectType)
            except AssertionError:
                return (
                    f"{node_expr_str_full(node.from_op.inputs[param_names[0]])}."
                    f"querytoobj({node_expr_str_full(node.from_op.inputs[param_names[1]])}, ?)"
                )
            else:
                return (
                    f"{node_expr_str_full(node.from_op.inputs[param_names[0]])}."
                    f"querytoobj({node_expr_str_full(node.from_op.inputs[param_names[1]])},"
                    f" {narrow_type.keyless_weave_type_class()})"
                )

        param_names = list(node.from_op.inputs.keys())
        if all(
            [not isinstance(n, graph.OutputNode) for n in node.from_op.inputs.values()]
        ):
            return "%s(%s)" % (
                graph.opuri_full_name(node.from_op.name),
                ", ".join(
                    node_expr_str_full(node.from_op.inputs[n]) for n in param_names
                ),
                # node.type.simple_str()[:100],
            )
        if not param_names:
            return "%s()" % graph.opuri_full_name(node.from_op.name)
        # This puts in newlines, but not very well. Fix me :)
        return "%s\n  .%s(%s) " % (
            node_expr_str_full(node.from_op.inputs[param_names[0]]),
            graph.opuri_full_name(node.from_op.name),
            ", ".join(
                node_expr_str_full(node.from_op.inputs[n]) for n in param_names[1:]
            ),
            # ""
            # node.type.simple_str()[:100],
        )
    elif isinstance(node, graph.ConstNode):
        if isinstance(node.type, types.Function):
            res = node_expr_str_full(node.val)

            res = textwrap.indent(res, "  ")
            return res
        try:
            str_val = str(node.val)
            if len(str_val) > 50:
                return f"~{str_val[:50]}...~"
            return str_val
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


def to_assignment_form(
    outputs: list[graph.Node],
) -> dict[graph.OutputNode, graph.VarNode]:
    fg = forward_graph.ForwardGraph(allow_var_nodes=True)
    fg.add_nodes(outputs)
    new_nodes: dict[graph.Node, graph.OutputNode] = {}
    assignments: dict[graph.Node, graph.VarNode] = {}
    next_assignment_roots = list(fg.roots)
    var_id = 0
    while next_assignment_roots:
        forward_node = next_assignment_roots.pop()
        node = forward_node.node
        node_inputs: dict[str, graph.Node] = {}
        for k, v in node.from_op.inputs.items():
            if v in assignments:
                node_inputs[k] = assignments[v]
            else:
                node_inputs[k] = v
        new_node = graph.OutputNode(node.type, node.from_op.name, node_inputs)

        # walk linear graph section, swapping nodes for variables pointing
        # assignments we've already created
        while len(forward_node.input_to) == 1:
            next_forward_node = list(forward_node.input_to)[0]
            next_node = next_forward_node.node
            next_node_inputs: dict[str, graph.Node] = {}
            for k, v in next_node.from_op.inputs.items():
                if v is node:
                    next_node_inputs[k] = new_node
                elif v in assignments:
                    next_node_inputs[k] = assignments[v]
                else:
                    next_node_inputs[k] = v
            new_node = graph.OutputNode(
                next_node.type, next_node.from_op.name, next_node_inputs
            )
            forward_node = next_forward_node
            node = next_node

        # store in assignment
        new_nodes[node] = new_node
        assignments[node] = graph.VarNode(node.type, f"var{var_id}")
        var_id += 1

        # if we have more than one input_to, then create those as roots
        if len(forward_node.input_to) > 1:
            for input_to in forward_node.input_to:
                if input_to not in next_assignment_roots:
                    next_assignment_roots.append(input_to)

        # else we have zero, this is terminal
    return {new_nodes[k]: v for k, v in assignments.items()}


def assignments_string(assignments: dict[graph.OutputNode, graph.VarNode]) -> str:
    return "\n".join(
        f"{str(var_node)} = {node_expr_str_full(expression)}"
        for expression, var_node in assignments.items()
    )
