import logging

from . import graph
from . import registry_mem
from . import weave_internal
from . import weave_types as types
from . import errors
from . import box
from . import compile
from . import engine_trace
from . import language_nullability
from .language_features.tagging import tag_store


def _fast_apply_map_fn(item, index, map_fn):
    if isinstance(map_fn, graph.OutputNode):
        inputs = {
            name: _fast_apply_map_fn(item, index, node)
            for name, node in map_fn.from_op.inputs.items()
        }
        op_def = registry_mem.memory_registry.get_op(map_fn.from_op.name)
        if language_nullability.should_force_none_result(inputs, op_def):
            return None
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
            # TODO: if map_fn.type is UnionType we should do something about it here
            # before we blow up in the Const(Type) constructor
            with tracer.trace("resolve_static:op.%s" % op_def.name):
                res = op_def.resolve_fn(**call_inputs)
                use_type = map_fn.type
                #
                # Note from Tim: It is completely possible and logically sound
                # to encounter a union type here. However during execution, we
                # will hit an error since const types raise when they are
                # unions. This raise is also logical and sound. The unfortunate
                # truth is that at this point we could be in any number of valid
                # member states of the union and don't "know" which one we are
                # in until we open the box and look inside. So, correctly
                # resolving the type requires looking at the data itself. I
                # wrote this code below to implement the fix, but it ended up
                # not being needed for the problem I was working on. Leaving
                # here for future reference, when it inevitably comes up again.
                #
                # if isinstance(use_type, types.UnionType):
                #     # WARNING: Expensive! maybe we should just allow unions in ConstNode?
                #     # Another idea: just strip off None or choose None based on null.
                #     res_type = types.TypeRegistry.type_of(res)
                #     if use_type.assign_type(res_type):
                #         use_type = res_type
                #     else:
                #         # Should we error here?
                #         pass
                return graph.ConstNode(use_type, res)
        return graph.OutputNode(map_fn.type, map_fn.from_op.name, inputs)
    elif isinstance(map_fn, graph.ConstNode):
        return map_fn
    elif isinstance(map_fn, graph.VarNode):
        return map_fn
    else:
        raise errors.WeaveInternalError("Invalid Node: %s" % map_fn)


def _can_fast_map(map_fn):
    async_op_nodes = graph.filter_nodes_full(
        [map_fn],
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

    # now map the remaining weave_fn (after resolving static branches above)
    # over the input list
    with tracer.trace("fast_map:map"):
        # push down tags from outer list to item
        list_tags = (
            None
            if not tag_store.is_tagged(input_list)
            else tag_store.get_tags(input_list)
        )
        result = []
        for i, item in enumerate(input_list):
            item_tags = tag_store.get_tags(item) if tag_store.is_tagged(item) else None
            item = box.box(item)
            with tag_store.new_tagging_context():
                if item_tags is not None:
                    tag_store.add_tags(item, item_tags)
                if list_tags is not None:
                    tag_store.add_tags(
                        item, list_tags, give_precedence_to_existing_tags=True
                    )
                item_result = _fast_apply_map_fn(item, i, map_fn)
                item_result_tags = (
                    tag_store.get_tags(item_result)
                    if tag_store.is_tagged(item_result)
                    else None
                )

            if item_result_tags is not None:
                tag_store.add_tags(item_result, item_result_tags)
            result.append(item_result)
        return result
