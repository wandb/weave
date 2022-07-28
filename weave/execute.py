import logging
from collections.abc import Mapping
from . import graph
from . import forward_graph
import pprint
import time
from . import artifacts_local
import threading
import typing
from . import engine_trace

# TODO: this won't be valid in a real scenario. We need to forward to an
# agent, that doesn't have the same memory registry
from . import errors
from . import registry_mem
from . import op_def
from . import execute_ids
from . import storage
from . import weave_types as types
from . import run_obj
from . import compile
from . import context
from . import uris
from . import box


class ExecuteStats:
    def __init__(self):
        self.node_stats = []

    def add_node(self, node, execution_time):
        self.node_stats.append((node, execution_time))

    def summary(self):
        op_counts = {}
        for node, t in self.node_stats:
            if isinstance(node, graph.OutputNode):
                op_counts.setdefault(node.from_op.name, {"count": 0, "total_time": 0})
                op_counts[node.from_op.name]["count"] += 1
                op_counts[node.from_op.name]["total_time"] += t
        for stats in op_counts.values():
            stats["avg_time"] = stats["total_time"] / stats["count"]
        sortable_stats = [(k, v) for k, v in op_counts.items()]

        return dict(
            list(reversed(sorted(sortable_stats, key=lambda s: s[1]["total_time"])))
        )


def execute_nodes(nodes, no_cache=False):
    print("nodes", nodes)
    nodes = compile.compile(nodes)
    print("compiled", nodes)
    fg = forward_graph.ForwardGraph(nodes)
    print("fg", fg)

    with context.execution_client():
        stats = execute_forward(fg, no_cache=no_cache)
    summary = stats.summary()
    logging.info("Execution summary\n%s" % pprint.pformat(summary))

    res = [fg.get_result(n) for n in nodes]
    print("res", res)
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
                execute_forward_node(fg, forward_node, no_cache=no_cache)
            except:
                logging.error(
                    "Exception during execution of: %s" % str(forward_node.node)
                )
                raise
            finally:
                if span is not None:
                    span.finish()
            stats.add_node(forward_node.node, time.time() - start_time)
        for forward_node in running_now:
            for downstream_forward_node in forward_node.input_to:
                ready_to_run = True
                for param_node in downstream_forward_node.node.from_op.inputs.values():
                    if not fg.has_result(param_node):
                        ready_to_run = False
                if ready_to_run:
                    to_run.add(downstream_forward_node)
    return stats


def async_op_body(run_uri, run_body, inputs):
    from . import api
    from .ops_primitives.weave_api import get as op_get

    with context.execution_client():
        run = op_get(run_uri)
        api.use(run.set_state("running"))
        dereffed_inputs = {}
        for input_name, input in inputs.items():
            dereffed_inputs[input_name] = storage.deref(input)
        run_body(**dereffed_inputs, _run=run)
        api.use(run.set_state("finished"))


def execute_async_op(
    op_def: op_def.OpDef, inputs: Mapping[str, typing.Any], run_id: str
):
    # TODO: should this be configurable with remote artifacts
    art_name = "run-%s" % run_id
    art_uri = uris.WeaveLocalArtifactURI.make_uri(
        artifacts_local.local_artifact_dir(), art_name, "latest"
    )
    job = threading.Thread(
        target=async_op_body, args=(art_uri, op_def.resolve_fn, inputs)
    )
    job.start()


def execute_sync_op(
    op_def: op_def.OpDef,
    inputs: Mapping[str, typing.Any],
):
    return op_def.resolve_fn(**inputs)


def is_run_op(op_call: graph.Op):
    self_node = op_call.inputs.get("self")
    if self_node is not None and isinstance(self_node.type, types.RunType):
        return True
    return False


def execute_forward_node(
    fg: forward_graph.ForwardGraph,
    forward_node: forward_graph.ForwardNode,
    no_cache=False,
):
    use_cache = not no_cache
    # use_cache = False
    node = forward_node.node
    if isinstance(node, graph.ConstNode):
        return

    logging.debug("Executing node: %s" % node)

    op_def = registry_mem.memory_registry.get_op(node.from_op.name)
    input_nodes = node.from_op.inputs

    input_refs = {}
    for input_name, input_node in input_nodes.items():
        input_refs[input_name] = fg.get_result(input_node)

    if use_cache or op_def.is_async:
        # Compute the run ID, which is deterministic if the op is pure
        run_id = execute_ids.make_run_id(op_def, input_refs)
        run_artifact_name = f"run-{run_id}"

    if use_cache and op_def.pure:
        run = storage.get_version(run_artifact_name, "latest")
        if run is not None:
            logging.debug("Cache hit, returning")
            # Watch out, we handle loading async runs in different ways.
            if op_def.is_async:
                forward_node.set_result(run)
                return
            else:
                if run._output is not None:
                    # if isinstance(run._output, artifacts_local.LocalArtifact):
                    #     print('OUTPUT REF TYPE OBJ TYPE', )
                    forward_node.set_result(run._output)
                    return
            logging.debug("Actually nevermind, didnt return")
            # otherwise, the run's output was not saveable, so we need
            # to recompute it.
    inputs = {
        input_name: storage.deref(input) for input_name, input in input_refs.items()
    }

    if op_def.is_async:
        logging.debug("Executing async op")
        run = run_obj.Run(run_id, op_def.name)
        input_refs = {}
        for input_name, input in inputs.items():
            ref = storage.get_ref(input)
            if ref is None:
                ref = storage.save(input)
            input_refs[input_name] = ref
        run._inputs = input_refs
        storage.save(run, name=run_artifact_name)
        execute_async_op(op_def, input_refs, run_id)
        forward_node.set_result(run)
    else:
        logging.debug("Executing sync op")

        # Hacking... this is nullability of ops
        # We should do this as a compile pass instead of hard-coding in engine.
        # That means we need an op called like "handle_null" that takes a function
        # as its second argument. Function is the op we want to execute if non-null.
        # TODO: fix
        # TODO: not implemented for async ops
        force_none_result = False
        if inputs:
            input_name0 = list(inputs.keys())[0]
            input0 = list(inputs.values())[0]
            if input0 is None or isinstance(input0, box.BoxedNone):
                input0_type = node.from_op.inputs[input_name0]
                if not types.is_optional(input0_type):
                    force_none_result = True
        if force_none_result:
            result = None
        else:
            result = execute_sync_op(op_def, inputs)

        ref = storage._get_ref(result)
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
                    output_name = "%s-output" % run_artifact_name
                try:
                    # Passing the node.type through here will really speed things up!
                    # But we can't do it yet because Weave Python function aren't all
                    # correctly typed, and WeaveJS sends down different types (like TagValues)
                    # TODO: Fix
                    result = storage.save(result, name=output_name)
                except errors.WeaveSerializeError:
                    # Not everything can be serialized currently. But instead of storing
                    # the result directly here, we save a MemRef with the same run_artifact_name.
                    # This is required to make downstream run_ids path dependent.
                    result = storage.save_mem(result, name=output_name)

        forward_node.set_result(result)

        # Don't save run ops as runs themselves.
        # TODO: This actually should work correctly, but mutation tracing
        #    does not really work yet. (mutated objects set their run output
        #    as the original ref rather than the new ref, which causes problems)
        if use_cache and not is_run_op(node.from_op):
            logging.debug("Saving run")
            run = run_obj.Run(run_id, op_def.name)
            run._inputs = input_refs
            run._output = result
            try:
                storage.save(run, name=run_artifact_name)
            except errors.WeaveSerializeError:
                pass
        logging.debug("Done executing node: %s" % node)
