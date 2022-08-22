from . import graph
from . import registry_mem
from . import weave_internal
from . import weave_types as types
from . import errors


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
                    "row": graph.ConstNode(types.Any(), row),
                    "index": graph.ConstNode(types.Number(), i),
                },
            )
        )
    return weave_internal.use(calls)


def fast_map_fn(input_list, map_fn):
    if not _can_fast_map(map_fn):
        return _slow_map_fn(input_list, map_fn)
    return [_fast_apply_map_fn(item, i, map_fn) for i, item in enumerate(input_list)]
