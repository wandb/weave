import copy
import typing

import logging
import contextvars
import contextlib

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


def _dispatch_map_fn_lambda_patch(
    node: graph.OutputNode,
    map_fn: typing.Callable[[graph.Node], typing.Optional[graph.Node]],
) -> graph.OutputNode:
    """
    This function is a helper function for the `_dispatch_map_fn_*` functions.
    It patches the "lambda ops", namely: map, filter, sort, and groupby (and
    their arrow equivalents). Specifically, each of these functions accept a
    lambda function that accepts a `row` parameter which is the `object_type` of
    the list-like input. Therefore, when doing the dispatch step in a full map,
    we need to update the `row` varnode type to be the `object_type` of the
    input. Ideally this would be a general solution that could leverage the
    callable input type on the op, but unfortunately, we cannot rely on the
    opdef of the incoming node to be correct yet! Therefore, we hardcode these
    specific ops by name ending (and make the assumption that the way to
    determine the `row` var type is by getting the `object_type` from the first
    input to the op).
    """
    if isinstance(node, graph.OutputNode) and (
        node.from_op.name.endswith("map")
        or node.from_op.name.endswith("filter")
        or node.from_op.name.endswith("sort")
        or node.from_op.name.endswith("groupby")
    ):
        # The first arg of map, filter, sort, groupby is the row variable.
        # We need to patch the lambda to take the row variable as the first
        # arg.
        first_arg_node = list(node.from_op.inputs.values())[0]
        first_arg_node_type = first_arg_node.type

        # TODO: HACK: Since the `_dispatch_map_fn_*` mappers run before the
        # `_call_run_await` and `_call_execute` mappers , the type is not going
        # to be correct in these cases. Unfortunately, we can't put those first,
        # since we need the dispatch to run first since those mappers rely on
        # the ops being correct. Sigh... this is a chicken/egg issue. In the
        # meantime, we have this small hack to fix the type.
        if isinstance(first_arg_node_type, types.Function):
            first_arg_node_type = first_arg_node_type.output_type
        elif isinstance(first_arg_node_type, types.RunType):
            first_arg_node_type = first_arg_node_type.output

        # Here, we check if there is an `object_type` on the input type. By
        # convention, our list-like types (list, ArrowWeaveList,
        # ArrowTableGroupBy) all have `object_type` to specify the type of the
        # elements.
        if not hasattr(first_arg_node_type, "object_type"):
            raise errors.WeaveInternalError(
                f"Expected {first_arg_node_type} to have an `object_type`"
            )
        row_node_type = first_arg_node_type.object_type  # type: ignore

        # Next, we iterate through the parameters and perform the patching in each
        # lambda function. In practice, we only expect there to be one lambda fn.
        new_inputs = {}
        needs_replacement = False
        for param_name, param_node in node.from_op.inputs.items():
            # Lambda params are identified by being a Const node of Function
            # type with a "row" input.
            if (
                isinstance(param_node, graph.ConstNode)
                and isinstance(param_node.type, types.Function)
                and "row" in param_node.type.input_types
            ):
                # If the existing lambda already supports the incoming row type,
                # then we don't need to patch it.
                if not param_node.type.input_types["row"].assign_type(row_node_type):
                    needs_replacement = True

                    # Here we make a shallow copy of the lambda function in case this lambda node
                    # is shared by multiple ops. In that case, we would do an in-place modification
                    # which might not be correct for all ops which consume this lambda.
                    lambda_fn_node = graph.ConstNode(
                        types.Function(
                            {**param_node.type.input_types},
                            param_node.type.output_type,
                        ),
                        param_node.val,
                    )

                    # Patch 1: Set the input type of the function
                    typing.cast(types.Function, lambda_fn_node.type).input_types[
                        "row"
                    ] = row_node_type

                    # Patch 2: Set all row var nodes to the correct type. We use
                    # a map_nodes_top_level because all we want to do is replace
                    # the row var node in the current lambda function.
                    # Importantly, this will retain ref equality for nodes which
                    # do not have the row var in their ancestry.
                    def patch_row_var_node(node: graph.Node) -> graph.Node:
                        if isinstance(node, graph.VarNode) and node.name == "row":
                            return graph.VarNode(row_node_type, "row")
                        return node

                    lambda_fn_node.val = graph.map_nodes_top_level(
                        [lambda_fn_node.val], patch_row_var_node
                    )[0]

                    # Patch 3: Apply the lambda function to the newly crafted
                    # node. TODO: There are 2 optimizations which we could do
                    # here:
                    # 1. Since this function is being called inside of a
                    #    map_nodes_full, we could share the `already_mapped`
                    #    cache to ensure we don't remap any node more than once.
                    #    This would require refactoring the map_nodes_*
                    #    functions to pass the cache around.
                    # 2. We could skip mapping into this lambda on the first
                    #    pass of map_nodes_full since it will be mapped here again.
                    lambda_fn_node.val = graph.map_nodes_full(
                        [lambda_fn_node.val], map_fn
                    )[0]

                    # Update the param node to be the new lambda node
                    param_node = lambda_fn_node
            new_inputs[param_name] = param_node

        # only return a new node if we actually patched one of the lambdas
        if needs_replacement:
            return graph.OutputNode(node.type, node.from_op.name, new_inputs)

    return node


def _dispatch_map_fn_refining(node: graph.Node) -> typing.Optional[graph.OutputNode]:
    if isinstance(node, graph.OutputNode):
        node = _dispatch_map_fn_lambda_patch(node, _dispatch_map_fn_refining)
        if node.from_op.name == "gqlroot-wbgqlquery":
            # the output type of the gqlroot-wbgqlquery op is Any. But the gql
            # compile phase keeps the original type from the root node that was
            # swapped in. We need that original type here so that downstream
            # dispatch works. So just return the node in this case instead of
            # dispatching.
            return node
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


def _remove_optional(t: types.Type) -> types.Type:
    if types.is_optional(t):
        return types.non_none(t)
    return t


def _dispatch_map_fn_no_refine(node: graph.Node) -> typing.Optional[graph.Node]:
    if isinstance(node, graph.OutputNode):
        node = _dispatch_map_fn_lambda_patch(node, _dispatch_map_fn_no_refine)
        if node.from_op.name == "tag-indexCheckpoint":
            # I'm seeing that there is no indexCheckpoint tag present
            # on types that come from WeaveJS (at least by the time we call
            # this op). Maybe a WeaveJS bug?
            # TODO
            return node
        if node.from_op.name == "file-type":
            # since we didn't refine, the input to file-type is not correct yet.
            # if its in the graph, just trust that's what we want
            # TODO: does this work for mapped case?
            return node
        node_inputs = node.from_op.inputs
        op = dispatch.get_op_for_inputs(node.from_op.name, [], node_inputs)
        params = node_inputs
        if isinstance(op.input_type, op_args.OpNamedArgs):
            params = {
                k: n for k, n in zip(op.input_type.arg_types, node_inputs.values())
            }

        # Weave Python op types don't express that they can handle
        # optional.
        output_type = _remove_optional(node.type)
        return graph.OutputNode(output_type, op.uri, params)
    return node


def _make_auto_op_map_fn(when_type: type[types.Type], call_op_fn):
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


_await_run_outputs_map_fn = _make_auto_op_map_fn(types.RunType, _call_run_await)

_execute_nodes_map_fn = _make_auto_op_map_fn(types.Function, _call_execute)


def _apply_column_pushdown(leaf_nodes: list[graph.Node]) -> list[graph.Node]:
    # This is specific to project-runs2 (not yet used in W&B production) for now. But it
    # is a general pattern that will work for all arrow tables.
    if not graph.filter_nodes_full(
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

    return graph.map_nodes_full(leaf_nodes, _replace_with_column_pushdown)


def _compile(nodes: typing.List[graph.Node]) -> typing.List[graph.Node]:
    tracer = engine_trace.tracer()
    logging.info("Starting compilation of graph with %s leaf nodes" % len(nodes))

    n = nodes

    # If we're being called from WeaveJS, we need to use dispatch to determine
    # which ops to use. Critically, this first phase does not actually refine
    # op output types, so after this, the types in the graph are not yet correct.
    with tracer.trace("compile:fix_calls"):
        n = graph.map_nodes_full(n, _dispatch_map_fn_no_refine)

    # Now that we have the correct calls, we can do our forward-looking pushdown
    # optimizations. These do not depend on having correct types in the graph.
    with tracer.trace("compile:gql"):
        n = compile_domain.apply_domain_op_gql_translation(n)
    with tracer.trace("compile:column_pushdown"):
        n = _apply_column_pushdown(n)

    # Auto-transforms, where we insert operations to convert between types
    # as needed.
    # TODO: is it ok to have this before final refine?
    with tracer.trace("compile:await"):
        n = graph.map_nodes_full(n, _await_run_outputs_map_fn)
    with tracer.trace("compile:execute"):
        n = graph.map_nodes_full(n, _execute_nodes_map_fn)

    # Final refine, to ensure the graph types are exactly what Weave python
    # produces. This phase can execute parts of the graph. It's very important
    # that this is the final phase, so that when we execute the rest of the
    # graph, we reuse any results produced in this phase, instead of re-executing
    # those nodes.
    with tracer.trace("compile:refine"):
        n = graph.map_nodes_full(n, _dispatch_map_fn_refining)

    loggable_nodes = graph_debug.combine_common_nodes(n)
    logging.info(
        "Compilation complete. Result nodes:\n%s",
        "\n".join(graph_debug.node_expr_str_full(n) for n in loggable_nodes),
    )

    return n


_currently_compiling: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_current_compiling", default=False
)


def _is_compiling() -> bool:
    return _currently_compiling.get()


@contextlib.contextmanager
def _compiling():
    token = _currently_compiling.set(True)
    try:
        yield
    finally:
        _currently_compiling.reset(token)


def compile(nodes: typing.List[graph.Node]) -> typing.List[graph.Node]:
    """
    This method is used to "compile" a list of nodes. Here we can add any
    optimizations or graph rewrites
    """
    # The refine phase may execute parts of the graph. Executing recursively
    # calls compile. Use context to ensure we only compile the top level
    # graph.
    if _is_compiling():
        return nodes
    with _compiling():
        return _compile(nodes)
