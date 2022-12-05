import logging

from . import graph
from . import registry_mem
from . import weave_internal
from . import weave_types as types
from . import errors
from . import op_def
from . import compile
from . import engine_trace


def _fast_apply_map_fn(item, index, map_fn):
    if isinstance(map_fn, graph.OutputNode):
        inputs = {
            name: _fast_apply_map_fn(item, index, node)
            for name, node in map_fn.from_op.inputs.items()
        }
        op_def = registry_mem.memory_registry.get_op(map_fn.from_op.name)
        return op_def.resolve_fn(**inputs)
    elif isinstance(map_fn, graph.ConstNode):
        return map_fn.val
    elif isinstance(map_fn, graph.VarNode):
        if map_fn.name == "row":
            return item
        elif map_fn.name == "index":
            return index
        else:
            raise errors.WeaveInternalError(
                "Encountered unknown variable: %s" % map_fn.name
            )
    else:
        raise errors.WeaveInternalError("Invalid Node: %s" % map_fn)


def _resolve_static_branches(map_fn):
    if isinstance(map_fn, graph.OutputNode):
        inputs = {
            name: _resolve_static_branches(node)
            for name, node in map_fn.from_op.inputs.items()
        }

        if map_fn.from_op.name == "function-__call__":
            # Special case to expand function calls
            if isinstance(inputs["self"], graph.ConstNode):
                return weave_internal.better_call_fn(
                    inputs["self"].val,
                    inputs["arg1"],
                )

        if all(isinstance(v, graph.ConstNode) for v in inputs.values()):
            op_def = registry_mem.memory_registry.get_op(map_fn.from_op.name)
            call_inputs = {name: node.val for name, node in inputs.items()}
            tracer = engine_trace.tracer()
            with tracer.trace("resolve_static:op.%s" % op_def.name):
                return graph.ConstNode(map_fn.type, op_def.resolve_fn(**call_inputs))
        return graph.OutputNode(map_fn.type, map_fn.from_op.name, inputs)
    elif isinstance(map_fn, graph.ConstNode):
        return map_fn
    elif isinstance(map_fn, graph.VarNode):
        return map_fn
    else:
        raise errors.WeaveInternalError("Invalid Node: %s" % map_fn)


def _can_fast_map(map_fn):
    async_op_nodes = graph.filter_nodes(
        map_fn,
        lambda n: isinstance(n, graph.OutputNode)
        and registry_mem.memory_registry.get_op(n.from_op.name).is_async,
    )
    return len(async_op_nodes) == 0


def _slow_map_fn(input_list, map_fn):
    calls = []
    for i, row in enumerate(input_list):
        calls.append(
            weave_internal.call_fn(
                map_fn,
                {
                    "row": graph.ConstNode(types.TypeRegistry.type_of(row), row),
                    "index": graph.ConstNode(types.Number(), i),
                },
            )
        )
    return weave_internal.use(calls)


def fast_map_fn(input_list, map_fn):
    """Maps a weave function over an input list, without using engine."""
    # TODO: Perform this recursively in the main compile pass
    tracer = engine_trace.tracer()
    with tracer.trace("fast_map:compile1"):
        map_fn = compile.compile([map_fn])[0]

    if not _can_fast_map(map_fn):
        logging.warning("Cannot fast map, falling back to slow map for: %s", map_fn)
        return _slow_map_fn(input_list, map_fn)

    # we can resolve any branches that do not have variable node ancestors
    # one time up front.
    with tracer.trace("fast_map:resolve_static"):
        map_fn = _resolve_static_branches(map_fn)
    # Need to compile again after resolving static branches.
    # For example, we may have fetched an expression out of a Const node.
    with tracer.trace("fast_map:compile2"):
        map_fn = compile.compile([map_fn])[0]

    # These are hacks because sometimes __len__ and __getitem__
    # are OpDefs, sometimes they are regular Python functions.
    # TODO: Fix this (eager behavior)
    if isinstance(input_list.__len__, op_def.OpDef):
        list_len = input_list.__len__.resolve_fn()
    else:
        list_len = len(input_list)

    if isinstance(input_list.__getitem__, op_def.OpDef):
        getitem = input_list.__getitem__.resolve_fn
    else:
        getitem = lambda input_list, index: input_list.__getitem__(index)

    # now map the remaining weave_fn (after resolving static branches above)
    # over the input list
    with tracer.trace("fast_map:map"):
        return [
            _fast_apply_map_fn(getitem(input_list, i), i, map_fn)
            for i in range(list_len)
        ]
