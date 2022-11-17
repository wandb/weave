import logging
from collections.abc import Mapping
import pprint
import time
import threading
import typing

# Libraries
from . import box
from . import engine_trace
from . import errors

# Planner/Compiler
from . import compile
from . import forward_graph
from . import graph
from . import graph_debug
from .language_features.tagging import tag_store
from . import weave_types as types

# Ops
from . import registry_mem
from . import op_def
from . import op_args

# Trace / cache
from . import trace_local
from . import refs

# Language Features
from . import language_nullability

TRACE_LOCAL = trace_local.TraceLocal()


class ExecuteStats:
    def __init__(self):
        self.node_stats = []

    def add_node(self, node, execution_time, cache_used):
        self.node_stats.append((node, execution_time, cache_used))

    def summary(self):
        op_counts = {}
        for node, t, cache_used in self.node_stats:
            if isinstance(node, graph.OutputNode):
                op_counts.setdefault(
                    node.from_op.name, {"count": 0, "total_time": 0, "cache_used": 0}
                )
                op_counts[node.from_op.name]["count"] += 1
                op_counts[node.from_op.name]["total_time"] += t
                op_counts[node.from_op.name]["cache_used"] += int(cache_used)
        for stats in op_counts.values():
            stats["avg_time"] = stats["total_time"] / stats["count"]
        sortable_stats = [(k, v) for k, v in op_counts.items()]

        return dict(
            list(reversed(sorted(sortable_stats, key=lambda s: s[1]["total_time"])))
        )


def is_panelplot_data_fetch_query(node: graph.Node) -> bool:
    if isinstance(node, graph.OutputNode) and node.from_op.name == "list":
        return all(
            map(
                lambda input: isinstance(input, graph.OutputNode)
                and input.from_op.name == "unnest",
                node.from_op.inputs.values(),
            )
        )
    return False


def execute_nodes(nodes, no_cache=False):
    logging.info(
        "Executing %s leaf nodes.\n%s"
        % (
            len(nodes),
            "\n".join(
                graph_debug.node_expr_str_full(n)
                for n in graph_debug.combine_common_nodes(nodes)
            ),
        )
    )
    nodes = compile.compile(nodes)

    # hack: disable caching for panelplot
    no_cache |= any([is_panelplot_data_fetch_query(node) for node in nodes])
    with tag_store.isolated_tagging_context():
        fg = forward_graph.ForwardGraph(nodes)

        stats = execute_forward(fg, no_cache=no_cache)
        summary = stats.summary()
        logging.info("Execution summary\n%s" % pprint.pformat(summary))

        res = [fg.get_result(n) for n in nodes]
    return res


def execute_forward(fg: forward_graph.ForwardGraph, no_cache=False) -> ExecuteStats:
    to_run: set[forward_graph.ForwardNode] = fg.roots

    stats = ExecuteStats()
    tracer = engine_trace.tracer()
    while len(to_run):
        running_now = to_run.copy()
        to_run = set()
        for forward_node in running_now:
            start_time = time.time()
            span = None
            if isinstance(forward_node.node, graph.OutputNode):
                span = tracer.trace(
                    "op.%s" % graph.op_full_name(forward_node.node.from_op)
                )
            try:
                with tag_store.set_curr_node(
                    id(forward_node.node),
                    [
                        id(input_node)
                        for input_node in forward_node.node.from_op.inputs.values()
                    ],
                ):
                    report = execute_forward_node(fg, forward_node, no_cache=no_cache)
            except:
                import traceback

                logging.error(
                    "Exception during execution of: %s\n%s"
                    % (str(forward_node.node), traceback.format_exc())
                )
                raise
            finally:
                if span is not None:
                    span.finish()
            stats.add_node(
                forward_node.node, time.time() - start_time, report["cache_used"]
            )
        for forward_node in running_now:
            for downstream_forward_node in forward_node.input_to:
                ready_to_run = True
                for param_node in downstream_forward_node.node.from_op.inputs.values():
                    if not fg.has_result(param_node):
                        ready_to_run = False
                if ready_to_run:
                    to_run.add(downstream_forward_node)
    return stats


def async_op_body(run_id, run_body, inputs):
    run = TRACE_LOCAL.get_run(run_id)
    run.state = "running"
    run.save()
    dereffed_inputs = {}
    for input_name, input in inputs.items():
        dereffed_inputs[input_name] = refs.deref(input)
    run_body(**dereffed_inputs, _run=run)
    run.state = "finished"
    run.save()


def execute_async_op(
    op_def: op_def.OpDef, inputs: Mapping[str, typing.Any], run_id: str
):
    job = threading.Thread(
        target=async_op_body,
        args=(run_id, op_def.resolve_fn, inputs),
    )
    job.start()


def execute_sync_op(
    op_def: op_def.OpDef,
    inputs: Mapping[str, typing.Any],
):
    return op_def.resolve_fn(**inputs)


def is_run_op(op_call: graph.Op):
    self_node = op_call.inputs.get("self")
    t = None
    if self_node is not None:
        t = self_node.type
    if self_node is not None and isinstance(self_node.type, types.RunType):
        return True
    return False


# the results of these ops will not be cached.
CACHE_DISALLOWLIST = [
    "list",
    "unnest",
]


class NodeExecutionReport(typing.TypedDict):
    cache_used: bool


def execute_forward_node(
    fg: forward_graph.ForwardGraph,
    forward_node: forward_graph.ForwardNode,
    no_cache=False,
) -> NodeExecutionReport:
    use_cache = not no_cache
    node = forward_node.node
    if isinstance(node, graph.ConstNode):
        return {"cache_used": False}

    logging.debug("Executing node: %s" % node)

    op_def = registry_mem.memory_registry.get_op(node.from_op.name)
    input_nodes = node.from_op.inputs

    # disable caching if op is in the cache disallowlist
    use_cache &= op_def.name not in CACHE_DISALLOWLIST

    input_refs: dict[str, refs.Ref] = {}
    for input_name, input_node in input_nodes.items():
        input_refs[input_name] = fg.get_result(input_node)

    if use_cache or op_def.is_async:
        # Compute the run ID, which is deterministic if the op is pure
        run_id = trace_local.make_run_id(op_def, input_refs)

    if use_cache and op_def.pure:
        run = TRACE_LOCAL.get_run(run_id)
        if run is not None:
            logging.debug("Cache hit, returning")
            # Watch out, we handle loading async runs in different ways.
            if op_def.is_async:
                forward_node.set_result(run)
                return {"cache_used": use_cache}
            else:
                if run.output is not None:
                    # if isinstance(run._output, artifacts_local.LocalArtifact):
                    #     print('OUTPUT REF TYPE OBJ TYPE', )
                    # This `refs.deref(run.output)` a critical call, even though
                    # the output is not used. This call ensures that the output
                    # is loaded, which in turn materializes the tags at the
                    # currect context scope. Without this call, the first child
                    # of this node will perform the derefing, which will result
                    # in the tags being added the the scope of the child. If
                    # more than 1 direct child exists, the next children will
                    # not have the tags in their scope.
                    refs.deref(run.output)
                    forward_node.set_result(run.output)
                    return {"cache_used": use_cache}
            logging.debug("Actually nevermind, didnt return")
            # otherwise, the run's output was not saveable, so we need
            # to recompute it.
    inputs = {input_name: refs.deref(input) for input_name, input in input_refs.items()}

    if op_def.is_async:
        logging.debug("Executing async op")
        input_refs = {}
        for input_name, input in inputs.items():
            ref = refs.get_ref(input)
            if ref is None:
                ref = TRACE_LOCAL.save_object(input)
            input_refs[input_name] = ref
        run = TRACE_LOCAL.new_run(run_id, op_def.name)
        run.inputs = input_refs
        run.save()

        execute_async_op(op_def, input_refs, run_id)
        forward_node.set_result(run)
    else:
        logging.debug("Executing sync op")
        if language_nullability.should_force_none_result(inputs, op_def):
            result = None
        else:
            result = execute_sync_op(op_def, inputs)

        ref = refs.get_ref(result)
        if ref is not None:
            logging.debug("Op resulted in ref")
            # If the op produced an object which has a ref (as in the case of get())
            # the result is the ref. This enables memoization after impure ops. E.g.
            # if get('x:latest') produces version x:1, we use x:1 for our make_run_id
            # calculation
            result = ref
        else:
            if use_cache:
                logging.debug("Saving result")
                # If an op is impure, its output is saved to a name that does not
                # include run ID. This means consuming pure runs will hit cache if
                # the output of an impure op is the same as it was last time.
                # However that also means we can traceback through impure ops if we want
                # to see the actual query that run for a given object.
                # TODO: revisit this behavior
                output_name = None
                if op_def.pure:
                    output_name = "run-%s-output" % run_id
                result = TRACE_LOCAL.save_object(result, name=output_name)

        forward_node.set_result(result)

        # Don't save run ops as runs themselves.
        # TODO: This actually should work correctly, but mutation tracing
        #    does not really work yet. (mutated objects set their run output
        #    as the original ref rather than the new ref, which causes problems)
        if use_cache and not is_run_op(node.from_op):
            logging.debug("Saving run")
            try:
                run = TRACE_LOCAL.new_run(run_id, op_def.name)
                run.inputs = input_refs
                run.output = result
                run.save()
            except errors.WeaveSerializeError:
                pass
        logging.debug("Done executing node: %s" % node)
    return {"cache_used": use_cache}
