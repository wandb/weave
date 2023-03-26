import logging
import contextlib
import contextvars
from collections.abc import Mapping
import pprint
import time
import threading
import typing

# Configuration
from . import wandb_api

# Libraries
from . import engine_trace
from . import errors
from . import context
from . import memo
from . import environment

# Planner/Compiler
from . import compile
from . import forward_graph
from . import graph
from . import graph_debug
from .language_features.tagging import tag_store
from . import weave_types as types
from . import box

# Ops
from . import registry_mem
from . import op_def
from .language_features.tagging import process_opdef_resolve_fn
from .language_features.tagging import opdef_util

# Trace / cache
from . import trace_local
from . import ref_base

# Language Features
from . import language_nullability

TRACE_LOCAL = trace_local.TraceLocal()

# Set this to true when debugging for costly, but detailed storyline of execution
PRINT_DEBUG = False


class OpExecuteStats(typing.TypedDict):
    avg_time: float
    cached_used: int
    already_executed: int
    count: int
    total_time: float


class ExecuteStats:
    def __init__(self):
        self.node_stats = []

    def add_node(self, node, execution_time, cache_used, already_executed):
        self.node_stats.append((node, execution_time, cache_used, already_executed))

    def summary(self) -> dict[str, OpExecuteStats]:
        op_counts: dict = {}
        for node, t, cache_used, already_executed in self.node_stats:
            if isinstance(node, graph.OutputNode):
                op_counts.setdefault(
                    node.from_op.name,
                    {
                        "count": 0,
                        "total_time": 0,
                        "cache_used": 0,
                        "already_executed": 0,
                    },
                )
                op_counts[node.from_op.name]["count"] += 1
                op_counts[node.from_op.name]["total_time"] += t
                op_counts[node.from_op.name]["cache_used"] += int(cache_used)
                if already_executed:
                    op_counts[node.from_op.name]["already_executed"] += 1
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


class FullStats(typing.TypedDict):
    node_count: int


_top_level_stats_ctx: contextvars.ContextVar[
    typing.Optional[FullStats]
] = contextvars.ContextVar("_top_level_stats_ctx", default=None)


@contextlib.contextmanager
def top_level_stats():
    """Will keep stats for nodes executed within this context, including recurisvely."""
    stats = _top_level_stats_ctx.get()
    token = None
    if stats is None:
        stats = {"node_count": 0}
        token = _top_level_stats_ctx.set(stats)
    try:
        yield stats
    finally:
        if token is not None:
            _top_level_stats_ctx.reset(token)


def get_top_level_stats() -> typing.Optional[FullStats]:
    return _top_level_stats_ctx.get()


def execute_nodes(nodes, no_cache=False):
    tracer = engine_trace.tracer()
    with tracer.trace("execute-log-graph"):
        logging.info(
            "Executing %s leaf nodes.\n%s"
            % (
                len(nodes),
                "\n".join([graph_debug.node_expr_str_full(n) for n in nodes])
                # graph_debug.assignments_string(
                #     graph_debug.to_assignment_form(
                #         graph_debug.combine_common_nodes(nodes)
                #     )
                # ),
            )
        )
    with wandb_api.from_environment():
        with memo.memo_storage():
            with tag_store.isolated_tagging_context():
                # Compile can recursively call execute_nodes during the final
                # refine phase. We are careful in compile to ensure that the nodes that
                # it executes in its final phase are the same nodes (by reference equality)
                # that it returns, because those nodes are we look up in the result
                # graph to determine if we need to execute or not.
                # The test_execute:test_we_dont_over_execute test will fail if this
                # assumption is violated.
                with forward_graph.node_result_store():
                    nodes = compile.compile(nodes)
                    fg = forward_graph.ForwardGraph()
                    fg.add_nodes(nodes)

                    with context.execution_client():
                        stats = execute_forward(fg, no_cache=no_cache)
                        summary = stats.summary()
                        logging.info("Execution summary\n%s" % pprint.pformat(summary))
                        if PRINT_DEBUG:
                            for node in nodes:
                                _debug_node_stack(fg, node)

                        res = [fg.get_result(n) for n in nodes]

    top_level_stats = get_top_level_stats()
    if top_level_stats is not None:
        top_level_stats["node_count"] += sum(
            stats["count"] for stats in summary.values()
        ) - sum(stats["already_executed"] for stats in summary.values())

    return res


def execute_forward(fg: forward_graph.ForwardGraph, no_cache=False) -> ExecuteStats:
    to_run = fg.roots

    stats = ExecuteStats()
    tracer = engine_trace.tracer()
    while len(to_run):
        running_now = list(to_run)
        to_run = {}
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

                logging.info(
                    "Exception during execution of: %s\n%s"
                    % (
                        graph_debug.node_expr_str_full(forward_node.node),
                        traceback.format_exc(),
                    )
                )
                raise
            finally:
                if span is not None:
                    span.finish()
            stats.add_node(
                forward_node.node,
                time.time() - start_time,
                report["cache_used"],
                report.get("already_executed"),
            )
        for forward_node in running_now:
            for downstream_forward_node in forward_node.input_to:
                ready_to_run = True
                for param_node in downstream_forward_node.node.from_op.inputs.values():
                    if not fg.has_result(param_node):
                        ready_to_run = False
                if ready_to_run:
                    to_run[downstream_forward_node] = True
    return stats


def async_op_body(run_id, run_body, inputs):
    run = TRACE_LOCAL.get_run(run_id)
    run.state = "running"
    run.save()
    dereffed_inputs = {}
    for input_name, input in inputs.items():
        dereffed_inputs[input_name] = ref_base.deref(input)
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


class NodeExecutionReport(typing.TypedDict):
    cache_used: bool
    already_executed: typing.Optional[bool]


# This function is not called in prod - but helpful when debugging
# to print out the entire stack of nodes that were executed.
def _debug_node_stack(
    fg: forward_graph.ForwardGraph, node: graph.Node, depth=0, prefix=""
):
    padding = " " * depth
    if isinstance(node, graph.OutputNode):
        input_nodes = node.from_op.inputs
        result = ref_base.deref(fg.get_result(node))
        res_str = str(result)[:100]
        print(f"{padding}{prefix}{node.from_op.name} = {res_str}")
        for input_name, input_node in input_nodes.items():
            _debug_node_stack(fg, input_node, depth=depth + 1, prefix=f"{input_name}:")
    elif isinstance(node, graph.ConstNode):
        val_str = str(node.val)[:100]
        print(f"{padding}{prefix}CONST = {val_str}")
    elif isinstance(node, graph.VarNode):
        print(f"{padding}{prefix}VAR({node.name})")
    elif isinstance(node, graph.VoidNode):
        print(f"{padding}{prefix}VOID")
    else:
        print(f"ERROR: {type(node)}")


def _tag_safe_deref(ref):
    res = ref_base.deref(ref)
    if tag_store.is_tagged(ref):
        return tag_store.add_tags(box.box(res), tag_store.get_tags(ref))
    return res


def execute_forward_node(
    fg: forward_graph.ForwardGraph,
    forward_node: forward_graph.ForwardNode,
    no_cache=False,
) -> NodeExecutionReport:
    node = forward_node.node
    if fg.has_result(node):
        return {"cache_used": False, "already_executed": True}

    cache_mode = environment.cache_mode()
    if cache_mode == environment.CacheMode.MINIMAL:
        no_cache = True
        if not node.from_op.name.startswith("mapped") and (
            node.from_op.name.endswith("file-table")
            or node.from_op.name.endswith("file-joinedTable")
            # or node.from_op.name.endswith("artifactVersion-file")
            # or node.from_op.name.endswith("FilesystemArtifact-file")
        ):
            # Always cache file-table for now. file-table converts from the W&B json
            # table format to the much faster Weave arrow format. Since Weave cache
            # is like permanent memoization, this means each W&B table we encounter will
            # only be converted once.
            # Also cache artifactVersion-file and FilesystemArtifact-file. They require
            # loading a wandb artifact, which right now makes a sequence of 3-5 requests
            # to the W&B API.
            no_cache = False

    use_cache = not no_cache
    if isinstance(node, graph.ConstNode):
        return {"cache_used": False}

    # This is expensive!
    logging.info(
        "Executing op: %s expr: %s"
        % (node.from_op.name, graph_debug.node_expr_str_full(node))
    )

    tracer = engine_trace.tracer()

    with tracer.trace("execute-read-cache"):
        op_def = registry_mem.memory_registry.get_op(node.from_op.name)
        input_nodes = node.from_op.inputs

        input_refs: dict[str, ref_base.Ref] = {}
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
                    return {"cache_used": True, "already_executed": False}
                else:
                    if run.output is not None:
                        output_ref = run.output
                        # We must deref here to restore tags
                        output = output_ref.get()

                        # Flowed tags are not cacheable(!),
                        # because they may contain graph dependent information,
                        # as in the case of gql tags that contain results for downstream
                        # nodes. So we fix that up here, by flowing tags and overriding
                        # the cached tags.
                        # Note, this only works for outer tags, not tags that are inside
                        # values. For those, we don't have a solution yet.
                        if opdef_util.should_flow_tags(op_def):
                            arg0_ref = next(iter(input_refs.values()))
                            arg0 = ref_base.deref(arg0_ref)

                            output = output_ref.get()

                            process_opdef_resolve_fn.flow_tags(arg0, output)

                        forward_node.set_result(output_ref)

                        return {"cache_used": True, "already_executed": False}
                # otherwise, the run's output was not saveable, so we need
                # to recompute it.
        inputs = {
            input_name: _tag_safe_deref(input)
            for input_name, input in input_refs.items()
        }

    if op_def.is_async:
        with tracer.trace("execute-async"):
            input_refs = {}
            for input_name, input in inputs.items():
                ref = ref_base.get_ref(input)
                if ref is None:
                    ref = TRACE_LOCAL.save_object(input)
                input_refs[input_name] = ref
            run = TRACE_LOCAL.new_run(run_id, op_def.name)
            run.inputs = input_refs
            run.save()

            execute_async_op(op_def, input_refs, run_id)
            forward_node.set_result(run)
    else:
        with tracer.trace("execute-sync"):
            if language_nullability.should_force_none_result(inputs, op_def):
                result = None
            else:
                result = execute_sync_op(op_def, inputs)

        with tracer.trace("execute-write-cache"):
            ref = ref_base.get_ref(result)

            if ref is not None:
                logging.debug("Op resulted in ref")
                # If the op produced an object which has a ref (as in the case of get())
                # the result is the ref. This enables memoization after impure ops. E.g.
                # if get('x:latest') produces version x:1, we use x:1 for our make_run_id
                # calculation

                # Add tags from the result to the ref
                if tag_store.is_tagged(result):
                    tag_store.add_tags(ref, tag_store.get_tags(result))
                result = ref
            else:
                if use_cache:
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
                run = TRACE_LOCAL.new_run(run_id, op_def.name)
                run.inputs = input_refs
                run.output = result
                run.save()
    return {"cache_used": False, "already_executed": False}
