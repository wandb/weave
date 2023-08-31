import logging
import typing

from . import graph
from . import execute
from . import registry_mem
from . import weave_internal
from . import weave_types as types
from . import errors
from . import box
from . import compile
from . import engine_trace
from . import forward_graph
from . import language_nullability
from .language_features.tagging import tag_store

from . import ref_base
from . import op_policy

# from . import object_context


def _execute_fn_no_engine(item, index, map_fn):
    # executes map_fn without using the execute engine.
    if isinstance(map_fn, graph.OutputNode):
        inputs = {
            name: _execute_fn_no_engine(item, index, node)
            for name, node in map_fn.from_op.inputs.items()
        }
        op_def = registry_mem.memory_registry.get_op(map_fn.from_op.name)
        if language_nullability.should_force_none_result(inputs, op_def):
            return None
        for key in inputs:
            if isinstance(inputs[key], ref_base.Ref):
                inputs[key] = inputs[key].get()
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
    result_store = forward_graph.get_node_result_store()
    if isinstance(map_fn, graph.OutputNode):
        if result_store.has(map_fn):
            return graph.ConstNode(map_fn.type, result_store[map_fn])

        inputs = {
            name: _resolve_static_branches(node)
            for name, node in map_fn.from_op.inputs.items()
        }

        if map_fn.from_op.name == "function-__call__":
            # Special case to expand function calls
            self = inputs["self"]
            if isinstance(self, graph.ConstNode):
                if isinstance(self.val, graph.ConstNode) and isinstance(
                    self.val.type, types.Function
                ):
                    self = self.val

                res = weave_internal.better_call_fn(
                    self,
                    inputs["arg1"],
                )
                fixed = compile.compile_fix_calls([res])[0]
                return _resolve_static_branches(fixed)

        if all(isinstance(v, graph.ConstNode) for v in inputs.values()):
            call_node = graph.OutputNode(map_fn.type, map_fn.from_op.name, inputs)

            # Don't compile here, we've already compiled.
            with compile.disable_compile():
                res = weave_internal.use(call_node)
            result_store[map_fn] = res
            return graph.ConstNode(map_fn.type, res)
        return graph.OutputNode(map_fn.type, map_fn.from_op.name, inputs)
    elif isinstance(map_fn, graph.ConstNode):
        return map_fn
    elif isinstance(map_fn, graph.VarNode):
        return map_fn
    else:
        raise errors.WeaveInternalError("Invalid Node: %s" % map_fn)


def op_can_be_async(op_name: str) -> bool:
    try:
        op = registry_mem.memory_registry.get_op(op_name)
    except errors.WeaveMissingOpDefError:
        return any(
            [
                o.is_async
                for o in registry_mem.memory_registry.find_ops_by_common_name(op_name)
            ]
        )
    return op.is_async


def _can_fast_map(map_fn):
    not_fastmappable_nodes = graph.filter_nodes_full(
        [map_fn],
        lambda n: isinstance(n, graph.OutputNode)
        and (
            op_can_be_async(n.from_op.name)
            or op_policy.should_cache(n.from_op.full_name)
            or op_policy.should_run_in_parallel(n.from_op.full_name)
        ),
    )
    return len(not_fastmappable_nodes) == 0


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

    if len(input_list) == 0:
        return []

    # TODO: Perform this recursively in the main compile pass
    tracer = engine_trace.tracer()

    # we can resolve any branches that do not have variable node ancestors
    # one time up front.
    with tracer.trace("fast_map:resolve_static"):
        map_fn = _resolve_static_branches(map_fn)
    # Need to compile again after resolving static branches.

    if not _can_fast_map(map_fn):
        logging.warning("Cannot fast map, falling back to slow map for: %s", map_fn)
        return _slow_map_fn(input_list, map_fn)

    # For example, we may have fetched an expression out of a Const node.
    with tracer.trace("fast_map:compile2"):
        map_fn = compile.compile([map_fn])[0]

    logging.info("Fast mapping with map_fn: %s", map_fn)
    # now map the remaining weave_fn (after resolving static branches above)
    # over the input list
    with tracer.trace("fast_map:map"):
        list_tags = (
            None
            if not tag_store.is_tagged(input_list)
            else tag_store.get_tags(input_list)
        )
        result = []
        for i, item in enumerate(input_list):
            item = box.box(item)
            if list_tags is not None:
                # push down list tags to elements, mirroring arrow map (apply_fn_node_with_tag_pushdown)
                tag_store.add_tags(
                    item, list_tags, give_precedence_to_existing_tags=True
                )

            item_result = _execute_fn_no_engine(item, i, map_fn)
            result.append(item_result)
        return result
