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
                    "row": graph.ConstNode(types.Any(), row),
                    "index": graph.ConstNode(types.Number(), i),
                },
            )
        )
    return weave_internal.use(calls)


def fast_map_fn(input_list, map_fn):
    if not _can_fast_map(map_fn):
        return _slow_map_fn(input_list, map_fn)

    map_fn = _resolve_static_branches(map_fn)
    return [_fast_apply_map_fn(item, i, map_fn) for i, item in enumerate(input_list)]
