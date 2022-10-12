import typing

from . import op_args
from . import weave_types as types
from . import graph
from . import graph_editable
from . import registry_mem
from . import errors
from . import dispatch
from . import op_def

# These call_* functions must match the actual op implementations.
# But we don't want to import the op definitions themselves here, since
# those depend on the decorators, which aren't defined in the engine.


def call_run_await_final_output(run_node: graph.Node) -> graph.OutputNode:
    run_node_type = typing.cast(types.RunType, run_node.type)
    return graph.OutputNode(run_node_type.output, "run-await", {"self": run_node})


def call_tag_unwrapper(tagged_node: graph.Node) -> graph.OutputNode:
    tagged_node_type = typing.cast(types.TaggedType, tagged_node.type)
    return graph.OutputNode(
        tagged_node_type._value,
        "tagged-unwrapTaggedValue",
        {"tagged_value": tagged_node},
    )


def call_execute(function_node: graph.Node) -> graph.OutputNode:
    function_node_type = typing.cast(types.Function, function_node.type)
    return graph.OutputNode(
        function_node_type.output_type, "execute", {"node": function_node}
    )


def nodes_to_edit_graph(nodes: typing.List[graph.Node]) -> graph_editable.EditGraph:
    edit_g = graph_editable.EditGraph()
    for node in nodes:
        edit_g.add_node(node)
    return edit_g


def edit_graph_to_nodes(
    edit_g: graph_editable.EditGraph, nodes: typing.List[graph.Node]
) -> typing.List[graph.Node]:
    return [edit_g.get_node(n) for n in nodes]


# Helper function to get the type of a node safely respecting constant types.
# TODO: This should be moved into the core node logic
def node_type(node: graph.Node) -> types.Type:
    if isinstance(node, graph.ConstNode) and not isinstance(node.type, types.Const):
        return types.Const(node.type, node.val)
    return node.type


def apply_type_based_dispatch(
    edit_g: graph_editable.EditGraph,
) -> graph_editable.EditGraph:
    """
    This method is responsible for attempting to re-dispatch ops based on their
    types. This is useful to solve for mappability, JS/Py differences, or any
    case where the provided op may not be the true op needed given the provided
    types. Importantly, it does rely on paramter ordering.
    """
    for node in edit_g.nodes:
        input_types = {k: node_type(v) for k, v in node.from_op.inputs.items()}
        found_op = dispatch.get_op_for_input_types(node.from_op.name, [], input_types)
        if found_op is None:
            # There is a parallel spot in lazy.py which has a similar comment
            # This indicates that we believe there is no valid op to accept the incoming types.
            # Before productionizing Weave, we should throw here - for now since assignability is
            # still a bit off, we are a bit more relaxed.
            # raise errors.WeaveInternalError(
            #     f"Could not find op for input types {pos_param_types} for node {node.from_op.name}"
            # )
            continue

        if found_op.uri != node.from_op.name:
            params = found_op.bind_params(
                [], found_op.input_type.create_param_dict([], node.from_op.inputs)
            )
            named_param_types = {k: node_type(v) for k, v in params.items()}
            edit_g.replace(
                node,
                graph.OutputNode(
                    found_op.return_type_of_arg_types(named_param_types),
                    found_op.uri,
                    params,
                ),
            )

    return edit_g


def await_run_outputs_edit_graph(
    edit_g: graph_editable.EditGraph,
) -> graph_editable.EditGraph:
    """Automatically insert Run.await_final_output steps as needed."""

    for orig, edge in edit_g.edges_with_replacements:
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
            if not expected_input_type.assign_type(actual_input_type.output):
                raise Exception(
                    "invalid type chaining for run. input_type: %s, op_input_type: %s"
                    % (actual_input_type, expected_input_type)
                )
            new_inputs = dict(edge.input_to.from_op.inputs)
            new_inputs[edge.input_name] = call_run_await_final_output(edge.output_of)
            edit_g.replace(
                orig.input_to,
                graph.OutputNode(
                    edge.input_to.type, edge.input_to.from_op.name, new_inputs
                ),
            )

    return edit_g


def unwrap_tagged_values(
    edit_g: graph_editable.EditGraph,
) -> graph_editable.EditGraph:
    """Automatically insert Run.await_final_output steps as needed."""

    for orig, edge in edit_g.edges_with_replacements:
        actual_input_type = edge.output_of.type
        op_def = registry_mem.memory_registry.get_op(edge.input_to.from_op.name)
        # if op_def.name == "tag-indexCheckpoint" or op_def.name == "Object-__getattr__":
        #     # These are supposed to be a passthrough op, we don't want to convert
        #     # it. TODO: Find a more general way, maybe by type inspection?
        #     continue
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
        if isinstance(actual_input_type, types.TaggedType) and not isinstance(
            expected_input_type, types.TaggedType
        ):
            if not expected_input_type.assign_type(actual_input_type._value):
                raise Exception(
                    "invalid type chaining for tagged value. input_type: %s, op_input_type: %s"
                    % (actual_input_type, expected_input_type)
                )
            # import pdb; pdb.set_trace()
            new_inputs = dict(edge.input_to.from_op.inputs)
            new_inputs[edge.input_name] = call_tag_unwrapper(edge.output_of)
            edit_g.replace(
                orig.input_to,
                graph.OutputNode(
                    edge.input_to.type, edge.input_to.from_op.name, new_inputs
                ),
            )

    for node in edit_g.nodes:
        outputs = edit_g.output_edges.get(node, [])
        if len(outputs) == 0:
            replaced = edit_g.get_node(node)
            if isinstance(replaced.type, types.TaggedType):
                # import pdb; pdb.set_trace()
                edit_g.replace(
                    node,
                    call_tag_unwrapper(replaced),
                )

    return edit_g


def execute_edit_graph(edit_g: graph_editable.EditGraph) -> graph_editable.EditGraph:
    """In cases where an input is a Node, execute the Node"""

    for orig, edge in edit_g.edges_with_replacements:
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

            new_inputs[edge.input_name] = call_execute(edge.output_of)
            edit_g.replace(
                orig.input_to,
                graph.OutputNode(
                    edge.input_to.type, edge.input_to.from_op.name, new_inputs
                ),
            )
    return edit_g


def compile(nodes: typing.List[graph.Node]) -> typing.List[graph.Node]:
    """
    This method is used to "compile" a list of nodes. Here we can add any
    optimizations or graph rewrites
    """

    # Convert the nodes to an editable graph data structure
    g = nodes_to_edit_graph(nodes)

    # Each of the following lines is a transformation pass of the graph:
    # 1: Adjust any Op calls based on type-based dispatching
    g = apply_type_based_dispatch(g)

    # 2: Add Await nodes for Runs
    g = await_run_outputs_edit_graph(g)

    # 3: Execute function nodes
    g = execute_edit_graph(g)

    # 4: Unwrap tagged values
    g = unwrap_tagged_values(g)

    # Reconstruct a node list that matches the original order from the transformed graph
    n = edit_graph_to_nodes(g, nodes)
    return n
