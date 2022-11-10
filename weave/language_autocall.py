# Language feature: Automatic function calling
#
# A Weave Node is a Function. If there are no variables in the Node's DAG,
# the node can be executed.
#
# If you have a Node[Function[..., int]], you may pass it in positions that
# expect int. We automatically insert an .execute() op when this type of
# call is detected.
#
# TODO: resolve ambiguities:
#   - should it work recursively? (Node[Function[..., Function[..., int]]])
#   - does this cause invalid type/name overlap and collisions?

import typing

from . import weave_types as types
from . import op_args
from . import graph
from . import registry_mem
from . import errors
from . import graph_editable


def update_input_types(
    op_input_type: op_args.OpArgs, actual_input_types: dict[str, types.Type]
):
    if not isinstance(op_input_type, op_args.OpNamedArgs):
        return actual_input_types
    expected_input_types = op_input_type.arg_types
    result = {}
    for k, t in actual_input_types.items():
        expected_input_type = expected_input_types[k]
        if isinstance(t, types.Function) and not isinstance(
            expected_input_type, types.Function
        ):
            result[k] = t.output_type
        else:
            result[k] = t
    return result


def node_methods_class(type_: types.Type):
    if not isinstance(type_, types.Function):
        return None, None
    function_output_type = type_.output_type
    if not hasattr(function_output_type, "NodeMethodsClass"):
        return None, None
    return (
        function_output_type.NodeMethodsClass,
        function_output_type.__class__.__name__,
    )


# We don't want to import the op definitions themselves here, since
# those depend on the decorators, which aren't defined in the engine.
def _call_execute(function_node: graph.Node) -> graph.OutputNode:
    function_node_type = typing.cast(types.Function, function_node.type)
    return graph.OutputNode(
        function_node_type.output_type, "execute", {"node": function_node}
    )


def execute_edit_graph(edit_g: graph_editable.EditGraph) -> graph_editable.EditGraph:
    """In cases where an input is a Node, execute the Node"""

    for edge in edit_g.edges_with_replacements:
        actual_input_type = edge.output_of.type
        op_def = registry_mem.memory_registry.get_op(edge.input_to.from_op.name)
        if not isinstance(op_def.input_type, op_args.OpNamedArgs):
            # Not correct... we'd want to walk these too!
            # TODO: fix
            continue
        # If the Node type is RunType, but the Op argument it is passed to
        # is not a RunType, insert an await_final_output operation to convert
        # the Node from a run to the run's output.
        try:
            expected_input_type = op_def.input_type.arg_types[edge.input_name]
        except KeyError:
            raise errors.WeaveInternalError(
                "OpDef (%s) missing input_name: %s" % (op_def.name, edge.input_name)
            )
        if isinstance(actual_input_type, types.Function) and not isinstance(
            expected_input_type, types.Function
        ):
            if not expected_input_type.assign_type(actual_input_type.output_type):
                raise Exception(
                    "invalid type chaining for Node. input_type: %s, op_input_type: %s"
                    % (actual_input_type, expected_input_type)
                )
            new_inputs = dict(edge.input_to.from_op.inputs)

            new_inputs[edge.input_name] = _call_execute(edge.output_of)
            edit_g.replace(
                edge.input_to,
                graph.OutputNode(
                    edge.input_to.type, edge.input_to.from_op.name, new_inputs
                ),
            )
    return edit_g
