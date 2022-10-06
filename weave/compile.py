import typing

from . import op_args
from . import weave_types as types
from . import graph
from . import graph_editable
from . import registry_mem
from . import errors
from . import language_autocall

# These call_* functions must match the actual op implementations.
# But we don't want to import the op definitions themselves here, since
# those depend on the decorators, which aren't defined in the engine.


def call_run_await_final_output(run_node: graph.Node) -> graph.OutputNode:
    run_node_type = typing.cast(types.RunType, run_node.type)
    return graph.OutputNode(run_node_type.output, "run-await", {"self": run_node})


# The two compile passes here follow exactly the same structure.
# They insert extra operations that resolve either a Promise() or a callable
# to its output type.
# This is a more general pattern, of inserting pure transforms.
# We could refactor to share code. Do it when we add a third with the
# same pattern.


def await_run_outputs(nodes: typing.List[graph.Node]):
    """Automatically insert Run.await_final_output steps as needed."""

    edit_g = graph_editable.EditGraph()
    for node in nodes:
        edit_g.add_node(node)

    for edge in edit_g.edges:
        actual_input_type = edge.output_of.type
        op_def = registry_mem.memory_registry.get_op(edge.input_to.from_op.name)
        if op_def.name == "tag-indexCheckpoint" or op_def.name == "Object-__getattr__":
            # These are supposed to be a passthrough op, we don't want to convert
            # it. TODO: Find a more general way, maybe by type inspection?
            continue
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
                expected_input_type.assign_type(actual_input_type.output)
                == types.Invalid()
            ):
                raise Exception(
                    "invalid type chaining for run. input_type: %s, op_input_type: %s"
                    % (actual_input_type, expected_input_type)
                )
            new_inputs = dict(edge.input_to.from_op.inputs)
            new_inputs[edge.input_name] = call_run_await_final_output(edge.output_of)
            edit_g.replace(
                edge.input_to,
                graph.OutputNode(
                    edge.input_to.type, edge.input_to.from_op.name, new_inputs
                ),
            )

    return [edit_g.get_node(n) for n in nodes]


def compile(nodes: typing.List[graph.Node]):
    nodes = await_run_outputs(nodes)

    # Call twice because there is a bug that makes it only work on
    # one argument at a time, and I have a demo where this needs to work
    # on both a and b in add(a, b).
    # I think some of Tim's future changes may have fixed this bug?
    # TODO: fix.
    nodes = language_autocall.insert_execute_nodes(nodes)
    nodes = language_autocall.insert_execute_nodes(nodes)

    return nodes
