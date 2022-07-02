import typing

from . import op_args
from . import weave_types as types
from . import graph
from . import graph_editable
from . import registry_mem
from . import errors

# The two compile passes here follow exactly the same structure.
# They insert extra operations that resolve either a Promise() or a callable
# to its output type.
# This is a more general pattern, of inserting pure transforms.
# We could refactor to share code. Do it when we add a third with the
# same pattern.


def await_run_outputs(nodes: typing.List[graph.Node]):
    """Automatically insert Run.await_final_output steps as needed."""
    from . import run_obj

    edit_g = graph_editable.EditGraph()
    for node in nodes:
        edit_g.add_node(node)

    for edge in edit_g.edges:
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
        if isinstance(actual_input_type, types.RunType) and not isinstance(
            expected_input_type, types.RunType
        ):
            if (
                expected_input_type.assign_type(actual_input_type._output)
                == types.Invalid()
            ):
                raise Exception(
                    "invalid type chaining for run. input_type: %s, op_input_type: %s"
                    % (actual_input_type, expected_input_type)
                )
            new_inputs = dict(edge.input_to.from_op.inputs)
            new_inputs[edge.input_name] = run_obj.Run.await_final_output(edge.output_of)
            edit_g.replace(
                edge.input_to,
                graph.OutputNode(
                    edge.input_to.type, edge.input_to.from_op.name, new_inputs
                ),
            )

    return [edit_g.get_node(n) for n in nodes]


def execute_nodes(nodes: typing.List[graph.Node]):
    """In cases where an input is a Node, execute the Node"""

    edit_g = graph_editable.EditGraph()
    for node in nodes:
        edit_g.add_node(node)

    for edge in edit_g.edges:
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
            if (
                expected_input_type.assign_type(actual_input_type.output_type)
                == types.Invalid()
            ):
                raise Exception(
                    "invalid type chaining for Node. input_type: %s, op_input_type: %s"
                    % (actual_input_type, expected_input_type)
                )
            new_inputs = dict(edge.input_to.from_op.inputs)
            from .ops_primitives.storage import execute

            new_inputs[edge.input_name] = execute(edge.output_of)
            edit_g.replace(
                edge.input_to,
                graph.OutputNode(
                    edge.input_to.type, edge.input_to.from_op.name, new_inputs
                ),
            )

    return [edit_g.get_node(n) for n in nodes]


def compile(nodes: typing.List[graph.Node]):
    nodes = await_run_outputs(nodes)
    nodes = execute_nodes(nodes)
    return nodes
