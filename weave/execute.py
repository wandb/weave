from collections.abc import Mapping
from . import graph
from . import forward_graph
import threading
import typing

# TODO: this won't be valid in a real scenario. We need to forward to an
# agent, that doesn't have the same memory registry
from . import errors
from . import registry_mem
from . import execute_ids
from . import storage
from . import weave_types as types
from . import run_obj
from . import compile
from . import context


def execute_nodes(nodes, no_cache=False):
    nodes = compile.compile(nodes)
    fg = forward_graph.ForwardGraph(nodes)

    with context.in_process_client():
        execute_forward(fg, no_cache=no_cache)

    return [fg.get_result(n) for n in nodes]


def execute_forward(fg: forward_graph.ForwardGraph, no_cache=False):
    to_run = fg.roots
    while len(to_run):
        running_now = to_run.copy()
        to_run = set()
        for forward_node in running_now:
            execute_forward_node(fg, forward_node, no_cache=no_cache)
        for forward_node in running_now:
            for downstream_forward_node in forward_node.input_to:
                ready_to_run = True
                for param_node in downstream_forward_node.node.from_op.inputs.values():
                    param_forward_node = fg.get_forward_node(param_node)
                    if not param_forward_node.has_result:
                        ready_to_run = False
                if ready_to_run:
                    to_run.add(downstream_forward_node)


def is_async_op(op_def: registry_mem.OpDef):
    return not callable(op_def.output_type) and op_def.output_type.name == "run-type"


def async_op_body(run_uri, run_body, inputs):
    from . import api
    from .ops_primitives import file

    with context.in_process_client():
        run = file.get(run_uri)
        api.use(run.set_state("running"))
        dereffed_inputs = {}
        for input_name, input in inputs.items():
            dereffed_inputs[input_name] = storage.deref(input)
        run_body(**dereffed_inputs, _run=run)
        api.use(run.set_state("finished"))


def execute_async_op(
    op_def: registry_mem.OpDef, inputs: Mapping[str, typing.Any], run_id: str
):
    art_name = "run-%s" % run_id
    job = threading.Thread(
        target=async_op_body, args=("%s/latest" % art_name, op_def.resolve_fn, inputs)
    )
    job.start()


def execute_sync_op(
    op_def: registry_mem.OpDef,
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
    node = forward_node.node
    if isinstance(node, graph.ConstNode):
        # node_id = storage.save(node.val)
        obj = node.val
        forward_node.set_result(obj)
        return
    elif isinstance(node, graph.VarNode):
        raise errors.WeaveInternalError("cannot execute VarNode: %s" % node)

    op_def = registry_mem.memory_registry.get_op(node.from_op.name)
    input_nodes = node.from_op.inputs

    input_refs = {}
    for input_name, input_node in input_nodes.items():
        input_refs[input_name] = fg.get_result(input_node)
    inputs = {
        input_name: storage.deref(input) for input_name, input in input_refs.items()
    }

    # Compute the run ID, which is deterministic if the op is pure
    run_id = execute_ids.make_run_id(op_def, input_refs)
    run_artifact_name = f"run-{run_id}"
    run = storage.get_version(run_artifact_name, "latest")

    if op_def.pure and run is not None:
        # Watch out, we handle loading async runs in different ways.
        if is_async_op(op_def):
            forward_node.set_result(run)
            return
        else:
            if run._output is not None:
                forward_node.set_result(run._output)
                return
            # otherwise, the run's output was not saveable, so we need
            # to recompute it.

    run = run_obj.Run(run_id, op_def.name)

    if is_async_op(op_def):
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
        run._inputs = input_refs

        result = execute_sync_op(op_def, inputs)
        ref = storage._get_ref(result)
        if ref is not None:
            # If the op produced an object which has a ref (as in the case of get())
            # the result is the ref. This enables memoization after impure ops. E.g.
            # if get('x:latest') produces version x:1, we use x:1 for our make_run_id
            # calculation
            result = ref
        else:
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
                result = storage.save(result, name=output_name)
            except errors.WeaveSerializeError:
                # Not everything can be serialized currently. But instead of storing
                # the result directly here, we save a MemRef with the same run_artifact_name.
                # This is required to make downstream run_ids path dependent.
                result = storage.save_mem(result, name=output_name)
        run._output = result

        forward_node.set_result(result)

        # Don't save run ops as runs themselves.
        # TODO: This actually should work correctly, but mutation tracing
        #    does not really work yet. (mutated objects set their run output
        #    as the original ref rather than the new ref, which causes problems)
        if not is_run_op(node.from_op):
            try:
                storage.save(run, name=run_artifact_name)
            except errors.WeaveSerializeError:
                pass
