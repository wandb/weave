import typing

import logging

from . import compile_domain
from . import op_args
from . import weave_types as types
from . import graph
from . import graph_editable
from . import registry_mem
from . import errors
from . import dispatch
from . import graph_debug
from . import stitch
from . import compile_table
from . import weave_internal

# These call_* functions must match the actual op implementations.
# But we don't want to import the op definitions themselves here, since
# those depend on the decorators, which aren't defined in the engine.


def call_run_await_final_output(run_node: graph.Node) -> graph.OutputNode:
    run_node_type = typing.cast(types.RunType, run_node.type)
    return graph.OutputNode(run_node_type.output, "run-await", {"self": run_node})


# We don't want to import the op definitions themselves here, since
# those depend on the decorators, which aren't defined in the engine.
def _call_execute(function_node: graph.Node) -> graph.OutputNode:
    function_node_type = typing.cast(types.Function, function_node.type)
    return graph.OutputNode(
        function_node_type.output_type, "execute", {"node": function_node}
    )


# Helper function to get the type of a node safely respecting constant types.
# TODO: This should be moved into the core node logic
def node_type(node: graph.Node) -> types.Type:
    if isinstance(node, graph.ConstNode) and not isinstance(node.type, types.Const):
        return types.Const(node.type, node.val)
    return node.type


def apply_type_based_dispatch(
    edit_g: graph_editable.EditGraph,
) -> None:
    """
    This method is responsible for attempting to re-dispatch ops based on their
    types. This is useful to solve for mappability, JS/Py differences, or any
    case where the provided op may not be the true op needed given the provided
    types. Importantly, it does rely on paramter ordering.
    """
    # Topological order guarantees that all parents have been processed before the children
    for orig_node in edit_g.topologically_ordered_nodes:
        node = edit_g.get_node(orig_node)
        node_inputs = {k: edit_g.get_node(v) for k, v in node.from_op.inputs.items()}
        new_node = dispatch.dispatch_by_name_and_type(
            node.from_op.name, [], node_inputs
        )
        should_replace = new_node.from_op.name != node.from_op.name or any(
            v in edit_g.replacements for v in orig_node.from_op.inputs.values()
        )
        if not node.type.assign_type(new_node.type):
            logging.warning(
                "Compile phase [dispatch] Changed output type for node %s from %s to %s. This indicates an incompability between WeaveJS and Weave Python",
                node,
                node.type,
                new_node.type,
            )
            should_replace = True

        # Due to a number of locations where the arg names differ between Weave0
        # and Weave1, it is possible that the types themselves are correct, but
        # the names are not. This is not a problem in execution but rather a
        # problem for other graph manipulation steps which leverage edge names.
        current_names = list(node.from_op.inputs.keys())
        new_names = list(new_node.from_op.inputs.keys())
        arg_names_differ = len(node.from_op.inputs) != len(
            new_node.from_op.inputs
        ) or any(n_k != o_k for n_k, o_k in zip(current_names, new_names))
        if arg_names_differ:
            logging.warning(
                "Compile phase [dispatch] Changed input arg names node %s from %s to %s. This indicates an mismatch between WeaveJS and Weave Python",
                node,
                ",".join(current_names),
                ",".join(new_names),
            )
            should_replace = True

        if should_replace:
            edit_g.replace(orig_node, new_node)


def await_run_outputs_edit_graph(
    edit_g: graph_editable.EditGraph,
) -> None:
    """Automatically insert Run.await_final_output steps as needed."""

    for orig_edge, edge in edit_g.edges_with_replacements:
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
                edge.input_to,
                graph.OutputNode(
                    edge.input_to.type, edge.input_to.from_op.name, new_inputs
                ),
            )


def execute_edit_graph(edit_g: graph_editable.EditGraph) -> None:
    """In cases where an input is a Node, execute the Node"""

    for orig_edge, edge in edit_g.edges_with_replacements:
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
                orig_edge.input_to,
                graph.OutputNode(
                    edge.input_to.type, edge.input_to.from_op.name, new_inputs
                ),
            )


def apply_column_pushdown(
    leaf_nodes: list[graph.Node],
) -> list[graph.Node]:
    # This is specific to project-runs2 (not yet used in W&B production) for now. But it
    # is a general pattern that will work for all arrow tables.
    if not graph.filter_all_nodes(
        leaf_nodes,
        lambda n: isinstance(n, graph.OutputNode) and n.from_op.name == "project-runs2",
    ):
        return leaf_nodes

    p = stitch.stitch(leaf_nodes)

    def _replace_with_column_pushdown(node: graph.Node) -> graph.Node:
        if isinstance(node, graph.OutputNode) and node.from_op.name == "project-runs2":
            forward_obj = p.get_result(node)
            run_cols = compile_table.get_projection(forward_obj)
            config_cols = list(run_cols.get("config", {}).keys())
            summary_cols = list(run_cols.get("summary", {}).keys())
            return graph.OutputNode(
                node.type,
                "project-runs2_with_columns",
                {
                    "project": node.from_op.inputs["project"],
                    "config_cols": weave_internal.const(config_cols),
                    "summary_cols": weave_internal.const(summary_cols),
                },
            )
        return node

    return graph.map_all_nodes(leaf_nodes, _replace_with_column_pushdown)


def _compile_phase(
    g: graph_editable.EditGraph,
    phase_name: str,
    phase_fn: typing.Callable[[graph_editable.EditGraph], None],
):
    phase_fn(g)
    edit_log = g.checkpoint()
    logging.info("Compile phase [%s] Made %s edits", phase_name, len(edit_log))
    if edit_log:
        loggable_nodes = graph_debug.combine_common_nodes(g.to_standard_graph())
        logging.info(
            "Compile phase [%s] Result nodes:\n%s",
            phase_name,
            "\n".join(graph_debug.node_expr_str_full(n) for n in loggable_nodes),
        )


def compile(nodes: typing.List[graph.Node]) -> typing.List[graph.Node]:
    """
    This method is used to "compile" a list of nodes. Here we can add any
    optimizations or graph rewrites
    """
    logging.info("Starting compilation of graph with %s leaf nodes" % len(nodes))

    # Convert the nodes to an editable graph data structure
    g = graph_editable.EditGraph(nodes)

    # Each of the following lines is a transformation pass of the graph:
    # 1: Adjust any Op calls based on type-based dispatching
    _compile_phase(g, "dispatch", apply_type_based_dispatch)

    # 2: Add Await nodes for Runs
    _compile_phase(g, "await", await_run_outputs_edit_graph)

    # 3: Execute function nodes
    _compile_phase(g, "execute", execute_edit_graph)

    # Reconstruct a node list that matches the original order from the transformed graph
    n = g.to_standard_graph()

    n = compile_domain.apply_domain_op_gql_translation(n)

    loggable_nodes = graph_debug.combine_common_nodes(n)
    logging.info(
        "Compile phase [pre-pushdown] Result nodes:\n%s",
        "\n".join(graph_debug.node_expr_str_full(n) for n in loggable_nodes),
    )
    n = apply_column_pushdown(n)
    loggable_nodes = graph_debug.combine_common_nodes(n)
    logging.info(
        "Compile phase [pushdown] Result nodes:\n%s",
        "\n".join(graph_debug.node_expr_str_full(n) for n in loggable_nodes),
    )

    logging.info("Compilation complete")

    return n
