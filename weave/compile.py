import re
import random
import typing

import logging
import contextvars
import contextlib


from . import value_or_error
from . import debug_compile


from . import serialize
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
from . import propagate_gql_keys
from . import input_provider
from . import partial_object
from . import gql_to_weave
from . import gql_op_plugin

from .language_features.tagging import tagged_value_type_helpers

# These call_* functions must match the actual op implementations.
# But we don't want to import the op definitions themselves here, since
# those depend on the decorators, which aren't defined in the engine.

DEBUG_COMPILE = False


def _dispatch_error_is_client_error(
    op_name: str, input_types: dict[str, types.Type]
) -> bool:
    from .ops_domain import wbmedia

    if op_name in set(
        (
            "tag-run",
            "count",
            "file-table",
            "offset",
            "typedDict-pick",
            "list-createIndexCheckpointTag",
            "entity-name",
            "concat",
            "string-isNumeric",
            "project-artifacts",
            "panel-table",
        )
    ):
        # All the cases we've seen of this lately are clearly client errors, so
        # we'll send back a 400!
        return True
    elif op_name == "file-path" and types.optional(
        wbmedia.ImageArtifactFileRefType()
    ).assign_type(input_types["file"]):
        # You shouldn't be able to call file-path on ImageArtifactFileRef.
        return True
    return False


def _call_run_await(run_node: graph.Node) -> graph.OutputNode:
    return graph.OutputNode(
        run_node.type.output_type.output, "run-await", {"self": run_node}  # type: ignore
    )


# We don't want to import the op definitions themselves here, since
# those depend on the decorators, which aren't defined in the engine.
def _call_execute(function_node: graph.Node) -> graph.OutputNode:
    function_node_type = typing.cast(types.Function, function_node.type)
    if isinstance(function_node, graph.ConstNode) and isinstance(
        function_node.val.type, types.Function
    ):
        return _call_execute(function_node.val)
    return graph.OutputNode(
        function_node_type.output_type, "execute", {"node": function_node}
    )


def _quote_node(node: graph.Node) -> graph.Node:
    return weave_internal.const(node)


def _static_function_types(node: graph.Node) -> typing.Optional[graph.Node]:
    # This compile time transform looks at all const-functions which have 0
    # inputs (we call these static lambdas). If it is a static lambda, then we
    # want to update the output type of the inner node and the function such
    # that the rest of the system has the correct types. This is needed because
    # we do not map into static lambdas and do not compile their inner contents
    # as it should be treated as a literal, quoted graph.
    if (
        isinstance(node, graph.ConstNode)
        and isinstance(node.type, types.Function)
        and len(node.type.input_types) == 0
    ):
        inner_node = node.val
        if isinstance(inner_node, graph.OutputNode):
            compiled_node = _compile([inner_node])[0]
            return weave_internal.const(
                weave_internal.make_output_node(
                    compiled_node.type,
                    inner_node.from_op.name,
                    inner_node.from_op.inputs,
                )
            )
    return None


def _remove_optional(t: types.Type) -> types.Type:
    if types.is_optional(t):
        return types.non_none(t)
    return t


def _dispatch_map_fn_no_refine(node: graph.Node) -> typing.Optional[graph.OutputNode]:
    if isinstance(node, graph.OutputNode):
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
        from_op = node.from_op
        op = None
        try:
            op = dispatch.get_op_for_inputs(node.from_op.name, from_op.input_types)
        except errors.WeaveDispatchError as e:
            # With the new DashUI implementation, we are not allowed to refine
            # nodes on the client. As a result, it is perfectly possible to
            # construct a graph manually (as is done when generating a template
            # from a table) where the nodes are under-typed. The result of this
            # is that we will fail to dispatch in this phase which short
            # circuits and errors early. This call to
            # `registry_mem.memory_registry.get_op(node.from_op.name)` is a
            # last-resort that blindly accepts the op by name (trusting that the
            # developer client-side constructed a good graph). Importantly, if
            # this is an invalid assumption, and the graph is truly incorrect,
            # the error will be thrown in the `compile_refine_and_propagate_gql`
            # step. This just permits the compilation to continue, given that
            # the above circumstance happens more frequently now.
            try:
                op = registry_mem.memory_registry.get_op(node.from_op.name)
            except errors.WeaveMissingOpDefError:
                pass
            if op is None:
                if _dispatch_error_is_client_error(from_op.name, from_op.input_types):
                    raise errors.WeaveBadRequest(
                        "Error while dispatching (no refine phase): %s. This is most likely a client error"
                        % from_op.name
                    )
                else:
                    raise

        params = from_op.inputs
        if isinstance(op.input_type, op_args.OpNamedArgs):
            params = {
                k: n for k, n in zip(op.input_type.arg_types, from_op.inputs.values())
            }

        output_type = node.type
        # In the case where we are dispatching to a new op, we want to use the
        # new op's `unrefined_output_type_for_params` output type - rather than
        # blindly trusting the client type.
        if not node.from_op.name.startswith("local-artifact://") and (
            # Why do we have to whitelist ops? Because we may have changed the input
            # types to, e.g. dict, which pass their inputs types through to their output
            # This solution doesn't feel generic, but it solves the boostrapping refinement
            # case on the LLM monitoring board. We refine all input nodes in the document.
            # Some of the refinement, like opMap, happens on the client side, rewriting the
            # type to be a regular list instead of ArrowWeaveList. When we get back here
            # to Python, we need that type to be ArrowWeaveList so it can be passed to withColumns.
            # If we don't whitelist dict and list, we'll pass the client type through here, which
            # is List, which will cause a dispatch error when we go to dispatch withColumns
            node.from_op.name == "dict"
            or node.from_op.name == "list"
            # We have to do this check because we do want to trust the client types in
            # many cases, like we have a get() that has already been refined. If we overwrite
            # that type here it would be "Any" and we won't be able to dispatch the next op.
            or node.from_op.name != op.name
        ):
            output_type = op.unrefined_output_type_for_params(params)

        # Consider: If the UI does a `callOpVeryUnsafe`, it is possible that the
        # graph is not correctly typed. Consider checking if they type is `Any`,
        # then we may want to use the concrete output type instead.

        res = graph.OutputNode(_remove_optional(output_type), op.uri, params)
        # logging.info("Dispatched (no refine): %s -> %s", node, res.type)
        return res
    return None


def _simple_optimizations(node: graph.Node) -> typing.Optional[graph.Node]:
    # Put simple graph transforms here!
    if not isinstance(node, graph.OutputNode):
        return None
    if node.from_op.friendly_name == "merge":
        # Merging two dicts where one is empty returns the other. The frontend
        # sends this pattern down a lot right now, and it causes us to break out
        # of arrow vectorization.
        lhs, rhs = node.from_op.inputs.values()
        if (
            isinstance(lhs, graph.OutputNode)
            and lhs.from_op.friendly_name == "dict"
            and not lhs.from_op.inputs
        ):
            return rhs
        if (
            isinstance(rhs, graph.OutputNode)
            and rhs.from_op.friendly_name == "dict"
            and not rhs.from_op.inputs
        ):
            return lhs
    elif isinstance(node, graph.OutputNode) and node.from_op.name == "count":
        # When the graph is `run.history.count`, we can avoid the more costly
        # loading of all run history and instead directly fetch the history
        # count from the server by reducing to `run.historyLineCount` which
        # compiles to a single gql edge. This is particularly helpful when
        # loading StreamTables backed by runs. It helps with the client-side map
        # refinement, table row count, and with logic that is conditioned on
        # empty tables
        arr_node = node.from_op.inputs["arr"]
        if isinstance(arr_node, graph.OutputNode) and arr_node.from_op.name.startswith(
            "run-history"
        ):
            run_node = arr_node.from_op.inputs["run"]
            return graph.OutputNode(
                node.type,
                "run-historyLineCount",
                {"run": run_node},
            )
    elif isinstance(node, graph.OutputNode) and node.from_op.name == "unique":
        # When the graph is `awl.keys.flatten.unique`, the user is really asking
        # for the columnNames. This can be reduced to a simple `awl.columnNames`
        # which is extremely fast as it is simply the property types of the
        # list!
        #
        # Note: we cannot perform such optimization on pure lists because we
        # don't have a way to operate on the type of the node itself.
        arr_node = node.from_op.inputs["arr"]
        if (
            isinstance(arr_node, graph.OutputNode)
            and arr_node.from_op.name == "ArrowWeaveList-flatten"
        ):
            arr_node_2 = arr_node.from_op.inputs["arr"]
            if (
                isinstance(arr_node_2, graph.OutputNode)
                and arr_node_2.from_op.name == "ArrowWeaveListTypedDict-keys"
            ):
                awl_node = arr_node_2.from_op.inputs["self"]
                return graph.OutputNode(
                    node.type, "ArrowWeaveListTypedDict-columnNames", {"self": awl_node}
                )
    return None


def _required_const_input_names(node: graph.OutputNode) -> typing.Optional[list[str]]:
    res = compile_domain.required_const_input_names(node)
    if res is not None:
        return res
    return None


def _resolve_required_consts(node: graph.Node) -> typing.Optional[graph.Node]:
    # Put simple graph transforms here!
    if not isinstance(node, graph.OutputNode):
        return None
    required_const_input_names = _required_const_input_names(node)
    if required_const_input_names is None:
        return None
    new_inputs = dict(node.from_op.inputs)
    for input_name, input_node in node.from_op.inputs.items():
        if input_name in required_const_input_names:
            if not isinstance(input_node, graph.ConstNode):
                result = weave_internal.use(_compile([input_node])[0])
                new_inputs[input_name] = graph.ConstNode(input_node.type, result)
    return graph.OutputNode(
        node.type,
        node.from_op.name,
        new_inputs,
    )


def _make_auto_op_map_fn(when_type: typing.Callable[[types.Type], bool], call_op_fn):
    def fn(node: graph.Node) -> typing.Optional[graph.Node]:
        if isinstance(node, graph.OutputNode):
            node_inputs = node.from_op.inputs
            op_def = registry_mem.memory_registry.get_op(node.from_op.name)
            if (
                op_def.name == "tag-indexCheckpoint"
                # or op_def.name == "Object-__getattr__"
                or op_def.name == "set"
                # panel_scatter and panel_distribution have the incorrect
                # input types for their config arg. They should be weave.Node.
                # We need a frontend fix to handle that. For now there's a hack
                # here.
                # TODO: Fix in frontend and panel_* and remove this hack.
                or (
                    isinstance(op_def.concrete_output_type, types.Type)
                    and op_def.concrete_output_type._base_type is not None
                    and op_def.concrete_output_type._base_type.name == "Panel"
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
                if not when_type(actual_input_type):
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
                if not when_type(op_input_type):
                    new_inputs[k] = call_op_fn(input_node)
                    swapped = True
            if swapped:
                return graph.OutputNode(node.type, node.from_op.name, new_inputs)
        return None

    return fn


def _make_inverse_auto_op_map_fn(when_type: type[types.Type], call_op_fn):
    def fn(node: graph.Node) -> typing.Optional[graph.Node]:
        if isinstance(node, graph.OutputNode):
            node_inputs = node.from_op.inputs
            op_def = registry_mem.memory_registry.get_op(node.from_op.name)
            new_inputs: dict[str, graph.Node] = {}
            for k, input_node in node_inputs.items():
                actual_input_type = input_node.type
                new_inputs[k] = input_node
                if isinstance(actual_input_type, when_type):
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
                if isinstance(op_input_type, when_type):
                    new_inputs[k] = call_op_fn(input_node)

            return graph.OutputNode(node.type, node.from_op.name, new_inputs)
        return None

    return fn


_await_run_outputs_map_fn = _make_auto_op_map_fn(
    lambda t: isinstance(t, types.Function)
    and isinstance(t.output_type, types.RunType),
    _call_run_await,
)

_execute_nodes_map_fn = _make_auto_op_map_fn(
    lambda t: isinstance(types.split_none(t)[1], types.Function), _call_execute
)

_quote_nodes_map_fn = _make_inverse_auto_op_map_fn(types.Function, _quote_node)


def compile_apply_column_pushdown(
    leaf_nodes: list[graph.Node], on_error: graph.OnErrorFnType = None
) -> list[graph.Node]:
    # This is specific to project-runs2 (not yet used in W&B production) for now. But it
    # is a general pattern that will work for all arrow tables.

    op_names = [
        "project-runs2",
        "run-history2",
        "mapped_run-history2",
        "run-history",
        "mapped_run-history",
        "run-history3",
        "mapped_run-history3",
    ]

    if not graph.filter_nodes_full(
        leaf_nodes,
        lambda n: isinstance(n, graph.OutputNode) and n.from_op.name in op_names,
    ):
        return leaf_nodes

    p = stitch.stitch(leaf_nodes, on_error=on_error)

    def _replace_with_column_pushdown(node: graph.Node) -> graph.Node:
        if isinstance(node, graph.OutputNode) and node.from_op.name in op_names:
            forward_obj = p.get_result(node)
            run_cols = compile_table.get_projection(forward_obj)
            if node.from_op.name == "project-runs2":
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
            if "run-history" in node.from_op.name:
                history_cols = list(run_cols.keys())

                if len(history_cols) > 0:
                    return graph.OutputNode(
                        node.type,
                        node.from_op.name + "_with_columns",
                        {
                            "run": node.from_op.inputs["run"],
                            "history_cols": weave_internal.const(
                                list(set([*history_cols, "_step"]))
                            ),
                        },
                    )
        return node

    return graph.map_nodes_full(leaf_nodes, _replace_with_column_pushdown, on_error)


def compile_dedupe(
    leaf_nodes: list[graph.Node], on_error: graph.OnErrorFnType = None
) -> list[graph.Node]:
    nodes: dict[str, graph.Node] = {}

    def _dedupe(node: graph.Node) -> graph.Node:
        from . import serialize

        node_id = serialize.node_id(node)
        if node_id in nodes:
            return nodes[node_id]
        nodes[node_id] = node
        return node

    return graph.map_nodes_full(leaf_nodes, _dedupe, on_error)


def compile_fix_calls(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    return graph.map_nodes_full(nodes, _dispatch_map_fn_no_refine, on_error)


def compile_simple_optimizations(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    return graph.map_nodes_full(nodes, _simple_optimizations, on_error)


def compile_resolve_required_consts(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    return graph.map_nodes_full(nodes, _resolve_required_consts, on_error)


def compile_await(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    return graph.map_nodes_full(nodes, _await_run_outputs_map_fn, on_error)


def compile_execute(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    # Actually does the execution here in compile phase.
    # I made this change to handle cases where we need to pass mutations through
    # execute calls, which happens when we have Nodes stored in Const nodes (panels)
    # that we are mutating.
    # However I think I later solved this with client-side execution and it can maybe
    # be removed.
    # I'm leaving this for now as it doesn't affect W&B prod (which never calls execute).
    with_execute_ops = graph.map_nodes_full(nodes, _execute_nodes_map_fn, on_error)
    return with_execute_ops

    def _replace_execute(node: graph.Node) -> typing.Optional[graph.Node]:
        if isinstance(node, graph.OutputNode) and node.from_op.name == "execute":
            res = weave_internal.use(node.from_op.inputs["node"])
            if not isinstance(res, graph.Node):
                raise ValueError(
                    f"Expected node to be a Node, got {res} of type {type(res)}"
                )
            return compile_fix_calls([res])[0]
        return None

    return graph.map_nodes_full(with_execute_ops, _replace_execute)


def _resolve_function_calls(node: graph.Node) -> typing.Optional[graph.Node]:
    if (
        not isinstance(node, graph.OutputNode)
        or node.from_op.name != "function-__call__"
    ):
        return node

    inputs = list(node.from_op.inputs.values())
    fn_node = inputs[0]
    if not (
        isinstance(fn_node, graph.ConstNode)
        and isinstance(fn_node.type, types.Function)
    ):
        return node

    while isinstance(fn_node.val, graph.ConstNode) and isinstance(
        fn_node.type, types.Function
    ):
        fn_node = fn_node.val

    return weave_internal.better_call_fn(fn_node, *inputs[1:])


def compile_function_calls(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    return graph.map_nodes_full(nodes, _resolve_function_calls, on_error)


def compile_quote(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    return graph.map_nodes_full(nodes, _quote_nodes_map_fn, on_error)


def compile_static_function_types(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    return graph.map_nodes_full(nodes, _static_function_types, on_error)


def _needs_gql_propagation(node: graph.OutputNode) -> bool:
    """Determines if a node needs to propagate the GQL keys of its inputs."""
    fq_opname = node.from_op.full_name
    opdef = registry_mem.memory_registry.get_op(fq_opname)
    plugin = gql_op_plugin.get_gql_plugin(opdef)
    first_arg_name = gql_op_plugin.first_arg_name(opdef)

    if first_arg_name is None:
        return False

    first_arg_type: types.Type = node.from_op.inputs[first_arg_name].type
    unwrapped_first_arg_type, _ = tagged_value_type_helpers.unwrap_tags(first_arg_type)

    if opdef.derived_from and opdef.derived_from.derived_ops["mapped"] == opdef:
        plugin = gql_op_plugin.get_gql_plugin(opdef.derived_from)
        unwrapped_first_arg_type = typing.cast(
            types.List, unwrapped_first_arg_type
        ).object_type

    return opdef.is_gql_root_resolver() or (
        plugin is not None
        and plugin.gql_op_output_type is not None
        and isinstance(unwrapped_first_arg_type, partial_object.PartialObjectType)
    )


def _initialize_gql_types_map_fn(node: graph.Node) -> typing.Optional[graph.Node]:
    if isinstance(node, graph.OutputNode):
        from_op = node.from_op

        if from_op.name == "gqlroot-wbgqlquery":
            # get the initial type
            assert "query_str" in from_op.inputs and isinstance(
                from_op.inputs["query_str"], graph.ConstNode
            )

            output_type = gql_to_weave.get_query_weave_type(
                compile_domain.normalize_gql_query_string(
                    from_op.inputs["query_str"].val
                )
            )

            return graph.OutputNode(
                output_type,
                "gqlroot-wbgqlquery",
                {
                    **from_op.inputs,
                    "output_type": graph.ConstNode(types.TypeType(), output_type),
                },
            )

        if from_op.name == "gqlroot-querytoobj":
            assert "gql_query_fragment" in from_op.inputs and isinstance(
                from_op.inputs["gql_query_fragment"], graph.ConstNode
            )
            inner_fragment = from_op.inputs["gql_query_fragment"].val

            assert "output_type" in from_op.inputs and isinstance(
                from_op.inputs["output_type"], graph.ConstNode
            )
            output_type = from_op.inputs["output_type"].val

            if isinstance(output_type, partial_object.PartialObjectTypeGeneratorType):
                key_type = typing.cast(
                    types.TypedDict,
                    gql_to_weave.get_query_weave_type(
                        compile_domain.normalize_gql_query_string(
                            compile_domain.fragment_to_query(inner_fragment)
                        )
                    ),
                )

                key = gql_to_weave.get_outermost_alias(inner_fragment)
                subtype = typing.cast(types.TypedDict, key_type.property_types[key])
                output_type = output_type.with_keys(subtype.property_types)

                return graph.OutputNode(
                    output_type,
                    "gqlroot-querytoobj",
                    {
                        **from_op.inputs,
                        "output_type": graph.ConstNode(types.TypeType(), output_type),
                    },
                )

    return node


def compile_initialize_gql_types(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    return graph.map_nodes_full(nodes, _initialize_gql_types_map_fn, on_error)


def _call_gql_propagate_keys(
    node: graph.OutputNode, p: stitch.StitchedGraph, original_node: graph.Node
) -> types.Type:
    """Calls the GQL key propagation function for a node."""

    const_node_input_vals = {
        key: value.val
        for key, value in node.from_op.inputs.items()
        if isinstance(value, graph.ConstNode)
    }
    ip = input_provider.InputAndStitchProvider(
        const_node_input_vals, p.get_result(original_node)
    )

    # Propagate GQL types
    return propagate_gql_keys.propagate_gql_keys(node, ip)


def compile_refine_and_propagate_gql(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    # Stitch is needed for gql key propagation only. If we try to stitch
    # a graph that does not have gqlroot-wbgqlquery, it may fail completely.
    # So we only stitch if we have a gqlroot-wbgqlquery node.

    use_stitch = (
        len(
            graph.filter_nodes_full(
                nodes,
                lambda n: isinstance(n, graph.OutputNode)
                and n.from_op.name == "gqlroot-wbgqlquery",
            )
        )
        > 0
    )

    # This lets us maintain a reverse mapping from the new nodes that are created
    # in the graph.map_nodes call to _dispatch_map_fn_refining to the original
    # nodes that were used in stitch. It's a bit hacky, but it allows us to store
    # the original nodes in the pre-dispatch graph as a list, then use a nonlocal
    # index to access them in _dispatch_map_fn_refining.
    p = stitch.stitch(nodes) if use_stitch else None
    node_array: list[graph.Node] = []

    def _ident(node: graph.Node) -> graph.Node:
        node_array.append(node)
        return node

    graph.map_nodes_full(nodes, _ident, on_error)

    i = -1

    def _dispatch_map_fn_refining(
        node: graph.Node,
    ) -> typing.Optional[graph.OutputNode]:
        # give us access to the index variable declared above
        nonlocal i
        i += 1

        if isinstance(node, graph.OutputNode):
            from_op = node.from_op

            if from_op.name == "gqlroot-wbgqlquery":
                # We skip the refine for this special node because we have already determined its type during
                # the initialize_gql_types phase, so it is already "refined". The lazy_call() below would wipe
                # that type out, leading to gql types not being propagated at all. So we skip it and use the
                # correct, previously calculated type from that phase.

                return node

            try:
                op = dispatch.get_op_for_inputs(from_op.name, from_op.input_types)
                params = from_op.inputs
                if isinstance(op.input_type, op_args.OpNamedArgs):
                    params = {
                        k: n
                        for k, n in zip(
                            op.input_type.arg_types, from_op.inputs.values()
                        )
                    }

                res = op.lazy_call(**params)

                # The GQL key propagation logic needs to happen in the refine pass rather than the GQL
                # compile pass. This is because the gql_op_output_types need refined input types or else
                # they can produce incorrect results. For example, consider this node:
                #
                #   root-project(...).filteredRuns(...).limit(1).run-summary()
                #                            .pick(my_table).file-table()
                #                            .table-rows().dropna().concat()
                #
                # During GQL compilation, the unrefined type of run-summary is:
                #
                #   TaggedValueType({...},
                #     List(object_type=TaggedValueType({['run']}, Dict(key_type=String(), object_type=Any()))))
                #
                # If we encounter ops without a gql_op_output_type, like pick(), we need to call
                # unrefined_output_type_for_params(). This can lead to invalid unrefined types propagating.
                #
                # In this example, after pick() and dropna() we end up with an invalid list type.
                # When concat() then calls its unrefined_output_type_for_params(), it errors because
                # we've passed an invalid list type to it.
                #
                # By propagating keys after refine, we avoid these unrefined type issues. Each
                # node's type has been refined before we propagate keys, so instead of Dict(String(), Any()),
                # we get the actual refined typedDict type.

                # We can't do GQL key propagation as a separate post-refine step today, because doing so
                # would that would re-run the whole graph if
                # nodes are modified after refine. We avoid this re-execution by doing propagation during
                # refine. In the future, if we can call compile_refine without triggering re-execution,
                # we could move this to a separate post-refine step.

                # We need the special gql_op_output_type instead of using callable output types because the
                # gql_op_output_type needs access to an InputProvider to traverse key trees and generate
                # aliases. Normal callable output types don't receive this.

                # Overall, propagating GQL keys during refine simplifies the logic by avoiding issues
                # around unrefined types and triggering re-execution when compared against doing it during the
                # compile_gql phase. However, it does couple the key propagation to the refine pass. Future
                # refactors could aim to decouple this, if we can avoid triggering re-execution.

                if p is not None and _needs_gql_propagation(res):
                    res.type = _call_gql_propagate_keys(res, p, node_array[i])

                # logging.info("Dispatched (refine): %s -> %s", node, res.type)
                return res
            except errors.WeaveDispatchError:
                logging.error(
                    "Error while dispatching (refine phase)\n!=!=!=!=!\nName: %s\nInput Types: %s\nExpression: %s",
                    from_op.name,
                    from_op.input_types,
                    re.sub(r'[\\]+"', '"', graph_debug.node_expr_str_full(node)),
                )
                if _dispatch_error_is_client_error(from_op.name, from_op.input_types):
                    err = errors.WeaveBadRequest(
                        "Error while dispatching: %s. This is most likely a client error"
                        % from_op.name
                    )
                    err.fingerprint = [
                        "error-while-dispatching-client-error",
                        from_op.name,
                    ]
                    raise err
                else:
                    raise
            except:
                logging.error(
                    "Error while dispatching (refine phase)\n!=!=!=!=!\nName: %s\nInput Types: %s\nExpression: %s",
                    from_op.name,
                    from_op.input_types,
                    re.sub(r'[\\]+"', '"', graph_debug.node_expr_str_full(node)),
                )
                raise

        return None

    return graph.map_nodes_full(nodes, _dispatch_map_fn_refining, on_error)


def _node_ops(node: graph.Node) -> typing.Optional[graph.Node]:
    if not isinstance(node, graph.OutputNode):
        return None

    # weavified ops are expanded here.
    op_def = registry_mem.memory_registry.get_op(node.from_op.name)
    if op_def.weave_fn is not None:
        return weave_internal.call_fn(op_def.weave_fn, node.from_op.inputs)

    # otherwise we expand this hard-coded list
    if node.from_op.name not in [
        "RunChain-history",
        "panel_table-active_data",
        "panel_table-active_row",
        "Query-selected",
        "panel_plot-selected_data",
        "panel_table-all_rows",
        "stream_table-rows",
        "panel_trace-active_span",
        "Facet-selected",
    ]:
        return None
    new_node = typing.cast(graph.Node, weave_internal.use(node))

    # The result will typically contain expressions that were sent down as
    # part of panel configs within Const nodes. They haven't been handled
    # by deserialize/compile yet.
    new_node_fixed_calls = compile_fix_calls([new_node])[0]

    # Do it again to handle nested calls
    return compile_node_ops([new_node_fixed_calls])[0]


def compile_node_ops(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    # Mission critical that we do not map into static lambdas. We do
    # not want to expand nodes that are meant by the caller to be interpreted
    # as their exact node.
    return graph.map_nodes_full(nodes, _node_ops, on_error)


# This compile pass using the `top_level` mapper since we recurse manually. We can't use
# the full mapper, because we need to traverse when encountering the lambda op itself,
# rather than the const node since we need uniqueness based on the lambda op.
def compile_lambda_uniqueness(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    return graph.map_nodes_top_level(nodes, _compile_lambda_uniqueness, on_error)


def _compile_lambda_uniqueness(node: graph.Node) -> typing.Optional[graph.Node]:
    # In the case that the node has a lambda op, then we recurse into any
    # lambda parameter. If the result is a new output var, then we update the
    # current node, ensuring that every lambda parameter is unique to the op.
    #
    # There is another benefit of this approach: parts of the lambda graph which are
    # shared between lambdas AND don't have a var ancestor will be shared in memory.
    # This means that if a lambda has a shared "non-dependent" parameter, then it will
    # only be executed once, and will be treated as the same logical op in stitch operations.
    # This is the desired behavior.
    if isinstance(node, graph.OutputNode):
        new_inputs = {}
        for input_key, input_node in node.from_op.inputs.items():
            if isinstance(input_node, graph.ConstNode) and isinstance(
                input_node.val, graph.Node
            ):
                uniq_lambda = compile_lambda_uniqueness([input_node.val])[0]
                if uniq_lambda is not input_node.val:
                    new_inputs[input_key] = graph.ConstNode(
                        input_node.type, uniq_lambda
                    )
        if len(new_inputs) > 0:
            use_inputs: dict[str, graph.Node] = {
                k: new_inputs.get(k, v) for k, v in node.from_op.inputs.items()
            }
            return weave_internal.make_output_node(
                node.type, node.from_op.name, use_inputs
            )

    # This is where the magic happens. We need to ensure that var nodes
    # are unique in memory
    elif isinstance(node, graph.VarNode):
        return weave_internal.make_var_node(node.type, node.name)

    return node


const_node = weave_internal.make_const_node(types.NoneType(), None)


def _track_errors(fn):
    def final(
        nodes: typing.List[graph.Node],
    ) -> value_or_error.ValueOrErrors[graph.Node]:
        compile_errors = []

        def on_error(ndx: int, e: Exception):
            compile_errors.append((ndx, e))
            return const_node

        inner_res = fn(nodes, on_error)

        results: list[value_or_error.ValueOrError[graph.Node]] = [
            value_or_error.Value(node) for node in inner_res
        ]
        for ndx, e in compile_errors:
            results[ndx] = value_or_error.Error(e)

        return value_or_error.ValueOrErrors(results)

    return final


def _compile(
    nodes: typing.List[graph.Node],
) -> value_or_error.ValueOrErrors[graph.Node]:
    tracer = engine_trace.tracer()
    # logging.info("Starting compilation of graph with %s leaf nodes" % len(nodes))

    results = value_or_error.ValueOrErrors.from_values(nodes)

    # If we're being called from WeaveJS, we need to use dispatch to determine
    # which ops to use. Critically, this first phase does not actually refine
    # op output types, so after this, the types in the graph are not yet correct.
    with tracer.trace("compile:fix_calls"):
        results = results.batch_map(_track_errors(compile_fix_calls))

    # Auto-transforms, where we insert operations to convert between types
    # as needed.
    # TODO: is it ok to have this before final refine?
    with tracer.trace("compile:await"):
        results = results.batch_map(_track_errors(compile_await))
    with tracer.trace("compile:execute"):
        results = results.batch_map(_track_errors(compile_execute))
    with tracer.trace("compile:function_calls"):
        results = results.batch_map(_track_errors(compile_function_calls))
    with tracer.trace("compile:quote"):
        # Mission critical to call `compile:quote` before and node re-writing
        # compilers such as compile:node_ops and compile:gql. Why?:
        #
        # It is useful to define a "static lambda". A "static lambda" is a const
        # node of type function with no inputs. This is used in our system to
        # represent a constant value which is a node. Useful for generating
        # boards or any sort of op that operates on nodes themselves.
        #
        # Moreover, this compile step will automatically "quote" inputs to ops
        # that expect node inputs - effectively making static lambdas when
        # called for.
        #
        # Furthermore, it is important to know that stream table rows (and many
        # other ops) now support expansion (meaning they get expanded into a
        # chain of new nodes in the compile pass).
        #
        # Conceptually, this created an issue: Compile passes that mutate nodes
        # (eg node expansion or gql compile) would modify the quoted node. But,
        # these functions that consume nodes do not want modified nodes.
        # Instead, we want the raw node that the caller intended. For this
        # reason we should always call compile:quote before any node re-writing.
        results = results.batch_map(_track_errors(compile_quote))

    with tracer.trace("compile:static_function_types"):
        results = results.batch_map(_track_errors(compile_static_function_types))

    # Some ops require const input nodes. This pass executes any branches necessary
    # to ensure that requirement holds.
    # Only gql ops require this for now.
    with tracer.trace("compile:resolve_required_consts"):
        results = results.batch_map(_track_errors(compile_resolve_required_consts))

    with tracer.trace("compile:node_ops"):
        results = results.batch_map(_track_errors(compile_node_ops))

    with tracer.trace("compile:simple_optimizations"):
        # Simple Optimizations should happen after `node_ops` to ensure we operate on
        # the expanded nodes.
        results = results.batch_map(_track_errors(compile_simple_optimizations))

    # The node ops phase above can expand nodes, leading to new nodes in the graph
    # that are potentially duplicates of others. dedupe will merge these nodes.
    with tracer.trace("compile:dedupe"):
        results = results.batch_map(_track_errors(compile_dedupe))

    # Stitch is used in stages following this one. Stitch requires that lambdas
    # are unique in memory if they are arguments to unique ops. We can receive
    # graphs that violate this requirement, and dedupe will happily merge lambdas
    # even if they are used in different ops. lambda_uniqueness pulls them back
    # apart.
    with tracer.trace("compile:lambda_uniqueness"):
        results = results.batch_map(_track_errors(compile_lambda_uniqueness))

    # Now that we have the correct calls, we can do our forward-looking pushdown
    # optimizations. These do not depend on having correct types in the graph.

    with tracer.trace("compile:gql_query"):
        results = results.batch_map(
            _track_errors(compile_domain.apply_domain_op_gql_translation)
        )

    with tracer.trace("compile:initialize_gql_types"):
        results = results.batch_map(_track_errors(compile_initialize_gql_types))

    with tracer.trace("compile:column_pushdown"):
        results = results.batch_map(_track_errors(compile_apply_column_pushdown))

    # Final refine, to ensure the graph types are exactly what Weave python
    # produces. This phase can execute parts of the graph. It's very important
    # that this is the final phase, so that when we execute the rest of the
    # graph, we reuse any results produced in this phase, instead of re-executing
    # those nodes.
    with tracer.trace("compile:refine_and_propagate_gql"):
        results = results.batch_map(_track_errors(compile_refine_and_propagate_gql))

    # This is very expensive!
    # loggable_nodes = graph_debug.combine_common_nodes(n)
    # logging.info(
    #     "Compilation complete. Result nodes:\n%s",
    #     "\n".join(graph_debug.node_expr_str_full(n) for n in loggable_nodes),
    # )

    if DEBUG_COMPILE:
        debug_compile.check_weave0_compile_result(
            nodes,
            [item if err == None else const_node for item, err in results.iter_items()],
        )

    return results


_compile_disabled: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_compile_disabled", default=False
)


def _is_compiling() -> bool:
    return _compile_disabled.get()


@contextlib.contextmanager
def disable_compile():
    token = _compile_disabled.set(True)
    try:
        yield
    finally:
        _compile_disabled.reset(token)


@contextlib.contextmanager
def enable_compile():
    token = _compile_disabled.set(False)
    try:
        yield
    finally:
        _compile_disabled.reset(token)


def compile(
    nodes: typing.List[graph.Node],
) -> value_or_error.ValueOrErrors[graph.Node]:
    """
    This method is used to "compile" a list of nodes. Here we can add any
    optimizations or graph rewrites
    """
    # The refine phase may execute parts of the graph. Executing recursively
    # calls compile. Use context to ensure we only compile the top level
    # graph.
    if _is_compiling():
        return value_or_error.ValueOrErrors.from_values(nodes)
    with disable_compile():
        return _compile(nodes)
