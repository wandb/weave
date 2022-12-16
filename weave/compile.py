import typing

import logging

from . import compile_domain
from . import op_args
from . import weave_types as types
from . import graph
from . import registry_mem
from . import dispatch
from . import graph_debug
from . import stitch
from . import compile_table
from . import weave_internal
from . import engine_trace
from . import errors
from . import environment
from .language_features.tagging import tagged_value_type

# These call_* functions must match the actual op implementations.
# But we don't want to import the op definitions themselves here, since
# those depend on the decorators, which aren't defined in the engine.


def _call_run_await(run_node: graph.Node) -> graph.OutputNode:
    run_node_type = typing.cast(types.RunType, run_node.type)
    return graph.OutputNode(run_node_type.output, "run-await", {"self": run_node})


# We don't want to import the op definitions themselves here, since
# those depend on the decorators, which aren't defined in the engine.
def _call_execute(function_node: graph.Node) -> graph.OutputNode:
    function_node_type = typing.cast(types.Function, function_node.type)
    return graph.OutputNode(
        function_node_type.output_type, "execute", {"node": function_node}
    )


def _fixup_output_type(graph_type: types.Type, op_type: types.Type):
    # graph_type is the type from the incoming graph, which is always already
    # refined by the caller.

    # op_type is the unrefined op output type, for the given inputs.

    # This function returns the equivalent to what the refined type should
    # be if were to refine now, but without actually doing the refine which
    # would execute the graph up to this point.

    # Doing refinement in the compile phase is bad. It means we have to double
    # compute ops (or worse). This happens because later phases need access
    # to the full graph to determine what to do (gql, column pushdown,
    # future optimizations)

    # We know that WeaveJS provides us with correctly refined types, but that
    # sometimes we have a more specific output type from the python op than
    # we do from the js op.

    # For example, file-table in WeavePython outputs an ArrowWeaveList instead
    # of a list.
    # In that case, we want to use the refined table object_type that WeaveJS
    # has already provided, but the more specific ArrowWeaveList container type.

    # Differences:
    #   we do mapped ops differently in python
    #   we do less tagging in python
    #   we have more specific list types in python
    #   weave python does not account for nullability in op types

    if isinstance(graph_type, tagged_value_type.TaggedValueType):
        if isinstance(op_type, tagged_value_type.TaggedValueType):
            # Always accept the graph type tags. Note, we don't try to fix the
            # tag types. We could...
            value = _fixup_output_type(graph_type.value, op_type.value)
        else:
            value = _fixup_output_type(graph_type.value, op_type)
        return tagged_value_type.TaggedValueType(graph_type.tag, value)

    graph_type_is_sub = op_type.assign_type(graph_type)
    op_type_is_sub = graph_type.assign_type(op_type)
    if graph_type_is_sub and op_type_is_sub:
        # types are equal
        return graph_type
    elif graph_type_is_sub:
        # graph type is more specific, accept it
        return graph_type
    elif op_type_is_sub:
        # op type is more specific, but its not refined. This happens when
        # we have a more specific list type.
        if isinstance(graph_type, types.List) and hasattr(op_type, "object_type"):
            # op_type is a more specific list type.
            object_type = _fixup_output_type(graph_type.object_type, op_type.object_type)  # type: ignore
            return op_type.__class__(object_type)  # type: ignore
        # This shouldn't happen, it indicates that we have a totally incorrect
        # type in WeaveJS. But this branch smooths over some issues for now.
        # TODO: Fix
        # raise errors.WeaveInternalError("Cannot fixup output type", graph_type, op_type)
        return op_type
    # Types disagree. Trust Weave Python type. WeaveJS is probably more "correct" but Weave Python
    # relies on its incorrectness.
    return op_type


def _dispatch_map_fn_refining(node: graph.Node) -> typing.Optional[graph.OutputNode]:
    if isinstance(node, graph.OutputNode):
        node_inputs = node.from_op.inputs
        new_node = dispatch.dispatch_by_name_and_type(
            node.from_op.name, [], node_inputs
        )
        should_replace = new_node.from_op.name != node.from_op.name
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
            return new_node
    return None


def _dispatch_map_fn(node: graph.Node) -> typing.Optional[graph.OutputNode]:
    if isinstance(node, graph.OutputNode):
        node_inputs = node.from_op.inputs
        op = dispatch.get_op_for_inputs(node.from_op.name, [], node_inputs)
        # params = op.bind_params(node_inputs.values(), {})
        params = node_inputs
        if isinstance(op.input_type, op_args.OpNamedArgs):
            params = {
                k: n for k, n in zip(op.input_type.arg_types, node_inputs.values())
            }
        output_type = op.unrefined_output_type_for_params(params)
        fixed_type = _fixup_output_type(node.type, output_type)
        return graph.OutputNode(fixed_type, op.uri, params)
    return None


def make_auto_op_map_fn(when_type: type[types.Type], call_op_fn):
    def fn(node: graph.Node) -> typing.Optional[graph.Node]:
        if isinstance(node, graph.OutputNode):
            node_inputs = node.from_op.inputs
            op_def = registry_mem.memory_registry.get_op(node.from_op.name)
            if (
                op_def.name == "tag-indexCheckpoint"
                or op_def.name == "Object-__getattr__"
                or op_def.name == "set"
                # panel_scatter and panel_distribution have the incorrect
                # input types for their config arg. They should be weave.Node.
                # We need a frontend fix to handle that. For now there's a hack
                # here.
                # TODO: Fix in frontend and panel_* and remove this hack.
                or (
                    isinstance(op_def.output_type, types.Type)
                    and op_def.output_type._base_type is not None
                    and op_def.output_type._base_type.name == "Panel"
                )
            ):
                # These are supposed to be a passthrough op, we don't want to convert
                # it. TODO: Find a more general way, maybe by type inspection?
                return None
            new_inputs: dict[str, graph.Node] = {}
            swapped = False
            for k, input_node in node_inputs.items():
                actual_input_type = input_node.type
                new_inputs[k] = input_node
                if not isinstance(actual_input_type, when_type):
                    continue
                if isinstance(op_def.input_type, op_args.OpNamedArgs):
                    op_input_type = op_def.input_type.arg_types[k]
                elif isinstance(op_def.input_type, op_args.OpVarArgs):
                    op_input_type = op_def.input_type.arg_type
                else:
                    raise ValueError(
                        f"Unexpected op input type {op_def.input_type} for op {op_def.name}"
                    )
                if callable(op_input_type):
                    continue
                if not isinstance(op_input_type, when_type):
                    new_inputs[k] = call_op_fn(input_node)
                    swapped = True
            if swapped:
                return graph.OutputNode(node.type, node.from_op.name, new_inputs)
        return None

    return fn


_await_run_outputs_map_fn = make_auto_op_map_fn(types.RunType, _call_run_await)

_execute_nodes_map_fn = make_auto_op_map_fn(types.Function, _call_execute)


def apply_column_pushdown(leaf_nodes: list[graph.Node]) -> list[graph.Node]:
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


def compile(nodes: typing.List[graph.Node]) -> typing.List[graph.Node]:
    """
    This method is used to "compile" a list of nodes. Here we can add any
    optimizations or graph rewrites
    """
    tracer = engine_trace.tracer()
    logging.info("Starting compilation of graph with %s leaf nodes" % len(nodes))

    n = nodes

    if environment.wandb_production():
        # First try dispatch without refine. If that doesn't work, fallback to the refining
        # version, and suffer a perf hit :(
        try:
            with tracer.trace("compile:dispatch1"):
                n = graph.map_all_nodes(n, _dispatch_map_fn)
        except errors.WeaveDispatchError:
            logging.warning("Falling back to refine dispatch.")
            with tracer.trace("compile:dispatch2"):
                n = graph.map_all_nodes(n, _dispatch_map_fn_refining)
    else:
        # when we're not in production, don't try to recover, we should fix these issues!
        with tracer.trace("compile:dispatch1"):
            n = graph.map_all_nodes(n, _dispatch_map_fn)

    with tracer.trace("compile:await"):
        n = graph.map_all_nodes(n, _await_run_outputs_map_fn)
    with tracer.trace("compile:execute"):
        n = graph.map_all_nodes(n, _execute_nodes_map_fn)
    with tracer.trace("compile:gql"):
        n = compile_domain.apply_domain_op_gql_translation(n)
    with tracer.trace("compile:column_pushdown"):
        n = apply_column_pushdown(n)

    loggable_nodes = graph_debug.combine_common_nodes(n)
    logging.info(
        "Compilation complete. Result nodes:\n%s",
        "\n".join(graph_debug.node_expr_str_full(n) for n in loggable_nodes),
    )

    return n
