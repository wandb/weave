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


def _dispatch_map_fn_refining(node: graph.Node) -> typing.Optional[graph.OutputNode]:
    if isinstance(node, graph.OutputNode):
        from_op = node.from_op
        try:
            op = dispatch.get_op_for_inputs(node.from_op.name, from_op.input_types)
            params = from_op.inputs
            if isinstance(op.input_type, op_args.OpNamedArgs):
                params = {
                    k: n
                    for k, n in zip(op.input_type.arg_types, from_op.inputs.values())
                }
            res = op.lazy_call(**params)
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
                raise errors.WeaveBadRequest(
                    "Error while dispatching: %s. This is most likely a client error"
                    % from_op.name
                )
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
        try:
            op = dispatch.get_op_for_inputs(node.from_op.name, from_op.input_types)
        except errors.WeaveDispatchError as e:
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
            node.from_op.name != op.name
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


def compile_refine(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    return graph.map_nodes_full(nodes, _dispatch_map_fn_refining, on_error)


def compile_merge_by_node_id(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    seen_nodes: dict[str, graph.Node] = {}

    def _merge_by_node_id(node: graph.Node) -> graph.Node:
        try:
            nid = serialize.node_id(node)
        except TypeError:
            nid = str(random.random())
        if nid in seen_nodes:
            return seen_nodes[nid]
        if isinstance(node, graph.OutputNode):
            node = dispatch.RuntimeOutputNode(
                node.type, node.from_op.name, node.from_op.inputs
            )
        elif isinstance(node, graph.VarNode):
            node = dispatch.RuntimeVarNode(node.type, node.name)
        elif isinstance(node, graph.ConstNode):
            node = dispatch.RuntimeConstNode(node.type, node.val)
        seen_nodes[nid] = node
        return node

    return graph.map_nodes_full(nodes, _merge_by_node_id, on_error)


def _node_ops(node: graph.Node) -> typing.Optional[graph.Node]:
    if not isinstance(node, graph.OutputNode):
        return None
    if node.from_op.name not in [
        "RunChain-history",
        "panel_table-active_data",
        "panel_table-active_row",
        "Query-selected",
        "panel_plot-selected_data",
        "panel_table-all_rows",
        "stream_table-rows",
    ]:
        return None
    new_node = typing.cast(graph.Node, weave_internal.use(node))

    # The result will typically contain expressions that were sent down as
    # part of panel configs within Const nodes. They haven't been handled
    # by deserialize/compile yet.
    new_node_fixed_calls = compile_fix_calls([new_node])[0]

    # This last line dedupes nodes that are identical. But it doesn't
    # globally dedupe against the graph we've already compiled.
    # There is still some duplication left in Weave execution...
    new_node_merged = compile_merge_by_node_id([new_node_fixed_calls])[0]

    # Do it again to handle nested calls
    return compile_node_ops([new_node_merged])[0]


def compile_node_ops(
    nodes: typing.List[graph.Node],
    on_error: graph.OnErrorFnType = None,
) -> typing.List[graph.Node]:
    # Mission critical that we do not map into static lambdas. We do
    # not want to expand nodes that are meant by the caller to be interpreted
    # as their exact node.
    return graph.map_nodes_full(nodes, _node_ops, on_error, True)


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

    with tracer.trace("compile:simple_optimizations"):
        results = results.batch_map(_track_errors(compile_simple_optimizations))

    with tracer.trace("compile:lambda_uniqueness"):
        results = results.batch_map(_track_errors(compile_lambda_uniqueness))

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

    # Some ops require const input nodes. This pass executes any branches necessary
    # to ensure that requirement holds.
    # Only gql ops require this for now.
    with tracer.trace("compile:resolve_required_consts"):
        results = results.batch_map(_track_errors(compile_resolve_required_consts))

    with tracer.trace("compile:node_ops"):
        results = results.batch_map(_track_errors(compile_node_ops))

    # Now that we have the correct calls, we can do our forward-looking pushdown
    # optimizations. These do not depend on having correct types in the graph.

    with tracer.trace("compile:gql"):
        results = results.batch_map(
            _track_errors(compile_domain.apply_domain_op_gql_translation)
        )

    with tracer.trace("compile:column_pushdown"):
        results = results.batch_map(_track_errors(compile_apply_column_pushdown))

    # Final refine, to ensure the graph types are exactly what Weave python
    # produces. This phase can execute parts of the graph. It's very important
    # that this is the final phase, so that when we execute the rest of the
    # graph, we reuse any results produced in this phase, instead of re-executing
    # those nodes.
    with tracer.trace("compile:refine"):
        results = results.batch_map(_track_errors(compile_refine))

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
def _compiling():
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
    with _compiling():
        return _compile(nodes)
