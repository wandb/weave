import logging
import typing
import pyarrow as pa
import numpy as np


from ..api import op, use
from .. import weave_types as types
from .. import graph
from .. import errors
from .. import registry_mem
from .. import op_def
from .. import dispatch
from .. import weave_internal
from .. import weavify

from .. import graph_debug

from .arrow import ArrowWeaveListType
from .list_ import ArrowWeaveList
from . import arraylist_ops
from . import convert_ops, convert
from .arrow_tags import pushdown_list_tags
from ..ops_primitives.dict import dict_
from ..ops_arrow.dict import preprocess_merge


class VectorizeError(errors.WeaveBaseError):
    pass


def make_vectorized_object_constructor(constructor_op_name: str) -> None:
    constructor_op = registry_mem.memory_registry.get_op(constructor_op_name)
    if callable(constructor_op.raw_output_type):
        raise errors.WeaveInternalError(
            "Unexpected. All object type constructors have fixed return types."
        )

    type_name = constructor_op.raw_output_type.name
    vectorized_constructor_op_name = f'ArrowWeaveList-{type_name.replace("-", "_")}'
    if registry_mem.memory_registry.have_op(vectorized_constructor_op_name):
        return

    output_type = ArrowWeaveListType(constructor_op.raw_output_type)

    @op(
        name=vectorized_constructor_op_name,
        input_type={
            "attributes": ArrowWeaveListType(
                constructor_op.input_type.weave_type().property_types["attributes"]  # type: ignore
            )
        },
        output_type=output_type,
        render_info={"type": "function"},
    )
    def vectorized_constructor(attributes):
        if callable(output_type):
            ot = output_type({"attributes": types.TypeRegistry.type_of(attributes)})
        else:
            ot = output_type
        return ArrowWeaveList(
            attributes._arrow_data, ot.object_type, attributes._artifact
        )


def _create_manually_mapped_op(
    op_name: str,
    inputs: typing.Dict[str, graph.Node],
    vectorized_keys: set[str],
):
    if len(vectorized_keys) == 1:
        return _create_manually_mapped_op_singular(
            op_name, inputs, list(vectorized_keys)[0]
        )
    op = registry_mem.memory_registry.get_op(op_name)
    inputs = _vectorized_inputs_as_awl_non_vectorized_as_lists(inputs, vectorized_keys)

    mapped_inputs = {k: v for k, v in inputs.items() if k in vectorized_keys}
    rest_inputs = {k: v for k, v in inputs.items() if k not in vectorized_keys}

    from . import dict

    input_arr = dict.arrow_dict_(**mapped_inputs).to_py()

    map_op = registry_mem.memory_registry.get_op("map")
    return map_op(
        input_arr,
        lambda input_dict: op(
            **{k: input_dict[k] for k in mapped_inputs}, **rest_inputs
        ),
    )


def _create_manually_mapped_op_singular(
    op_name: str,
    inputs: typing.Dict[str, graph.Node],
    vectorized_key: str,
):
    op = registry_mem.memory_registry.get_op(op_name)

    # We want to keep our vectorized inputs as AWL, even though we're going to use
    # listmap. Converting to python converts recursively, so if there are inner AWLs
    # -- as is the case in the output of AWL.groupby() which is
    # AWL<Tagged<..., AWL<...>> -- we want to keep those as AWLs. This way
    # AWL.groupby().map(lambda x: x.groupby()) will correctly keep all of the data
    # in arrow and use the arrow groupby for the inner call.

    inputs = _vectorized_inputs_as_awl_non_vectorized_as_lists(
        inputs, set([vectorized_key])
    )

    rest_inputs = {k: v for k, v in inputs.items() if k != vectorized_key}

    input_arr = inputs[vectorized_key]

    map_op = registry_mem.memory_registry.get_op("_listmap")
    return map_op(
        input_arr,
        lambda row: op(**{vectorized_key: row}, **rest_inputs),
    )


def _type_is_assignable_to_awl_list(t: types.Type) -> bool:
    return ArrowWeaveListType().assign_type(t)


def _type_is_assignable_to_py_list_not_awl_list(t: types.Type) -> bool:
    return types.List().assign_type(t) and not _type_is_assignable_to_awl_list(t)


def _ensure_list_like_node_is_awl(node: graph.Node) -> graph.Node:
    """
    Ensures that the node is an ArrowWeaveList by appending a conversion op (or stripping
    off an existing conversion op if possible)
    """
    if _type_is_assignable_to_awl_list(node.type):
        return node
    elif _type_is_assignable_to_py_list_not_awl_list(node.type):
        if (
            isinstance(node, graph.OutputNode)
            and node.from_op.name == "ArrowWeaveList-to_py"
        ):
            return list(node.from_op.inputs.values())[0]
        else:
            return convert_ops.list_to_arrow(node)
    else:
        return node


def _ensure_list_like_node_is_list(node: graph.Node) -> graph.Node:
    """
    Ensures that the node is an list by appending a conversion op (or stripping
    off an existing conversion op if possible)
    """
    if _type_is_assignable_to_py_list_not_awl_list(node.type):
        return node
    elif _type_is_assignable_to_awl_list(node.type):
        if (
            isinstance(node, graph.OutputNode)
            and node.from_op.name == "op-list_to_arrow"
        ):
            return list(node.from_op.inputs.values())[0]
        else:
            return convert_ops.to_py(node)
    else:
        return node


def _process_vectorized_inputs(
    inputs: dict[str, graph.Node],
    vectorized_keys: set[str],
    on_path: typing.Optional[typing.Callable] = None,
    off_path: typing.Optional[typing.Callable] = None,
) -> dict[str, graph.Node]:
    def identity(x):
        return x

    if on_path is None:
        on_path = identity
    if off_path is None:
        off_path = identity
    return {
        k: (on_path(in_node) if k in vectorized_keys else off_path(in_node))
        for k, in_node in inputs.items()
    }


def _vectorized_inputs_as_list(
    inputs: dict[str, graph.Node], vectorized_keys: set[str]
) -> dict[str, graph.Node]:
    return _process_vectorized_inputs(
        inputs, vectorized_keys, on_path=_ensure_list_like_node_is_list
    )


def _vectorized_inputs_as_awl(
    inputs: dict[str, graph.Node], vectorized_keys: set[str]
) -> dict[str, graph.Node]:
    return _process_vectorized_inputs(
        inputs, vectorized_keys, on_path=_ensure_list_like_node_is_awl
    )


def _vectorized_inputs_as_awl_non_vectorized_as_lists(
    inputs: dict[str, graph.Node], vectorized_keys: set[str]
) -> dict[str, graph.Node]:
    return _process_vectorized_inputs(
        inputs,
        vectorized_keys,
        on_path=_ensure_list_like_node_is_awl,
        off_path=_ensure_list_like_node_is_list,
    )


def _vectorize_lambda_output_node(node: graph.OutputNode, vectorized_keys: set[str]):
    # In a situation where we are trying to vectorize a "lambda"
    # function and the input is a a weave arrow list, then we are ina
    # bit of a pickle. This means we are trying to vectorize applying
    # this lambda to each element of the AWL. For example:
    # awl([[{"a":1, "b": 1}, {"a": 1, "b": 2}], [{"a": 2, "b": 3}, {"a": 2, "b": 4}]]).map(lambda row: row.groupby(lambda row: row["a"]))
    # When we hit the inner groupby, we are in this case. This is not
    # possible to vectorize grouping inside of a map. I think we could
    # figure out how to support nested mapping, but all the other pairs
    # are not possible to vectorize (to my knowledge). Therefore, in
    # these cases, we want to forcibly bail out to the list map which
    # does a `execute_fast.fast_map_fn` on each element of the list.
    return _create_manually_mapped_op_singular(
        node.from_op.name,
        node.from_op.inputs,
        next(iter(node.from_op.inputs)),
    )


def _is_lambda_output_node(node: graph.OutputNode):
    return (
        node.from_op.name.endswith("map")
        or node.from_op.name.endswith("groupby")
        or node.from_op.name.endswith("filter")
        or node.from_op.name.endswith("sort")
    )


def _is_non_simd_node(node: graph.OutputNode, vectorized_keys: set[str]):
    # These are ops (List/AWL) that are NOT SIMD (Single instruction, multiple data). This list is a hand
    # curated list from looking at Weave0. We probably need to refactor this entire vectorize to have a more
    # rigorous ruleset that can be applied, but in the interest of time, we are hand-crafting this for now
    non_vectorized_awl_op_names = [
        "limit",
        "offset",
        "unnest",
        "flatten",
        "2DProjection",
        "count",  # this is now SIMD
        "joinToStr",
        "unique",
        "numbers-sum",  # this is now SIMD
        "numbers-avg",  # this is now SIMD
        "numbers-argmax",
        "numbers-argmin",
        "numbers-stddev",
        "numbers-min",  # this is now SIMD
        "numbers-max",  # this is now SIMD
    ]
    first_arg_is_vectorized = list(node.from_op.inputs.keys())[0] in vectorized_keys
    return first_arg_is_vectorized and any(
        node.from_op.name.endswith(op_name) for op_name in non_vectorized_awl_op_names
    )


def _safe_get_op_for_inputs(
    name: str, inputs: dict[str, graph.Node]
) -> typing.Optional[op_def.OpDef]:
    try:
        return dispatch.get_op_for_inputs(name, {k: v.type for k, v in inputs.items()})
    except errors.WeaveDispatchError:
        return None


def _safe_get_weavified_op(op: op_def.OpDef) -> typing.Optional[graph.Node]:
    if op.weave_fn is None:
        try:
            op.weave_fn = weavify.op_to_weave_fn(op)
        except (
            errors.WeaveInternalError,
            errors.WeavifyError,
            errors.WeaveDispatchError,
            errors.WeaveTypeError,
        ):
            pass

    return op.weave_fn


def _vectorize_list_special_case(node_name, node_inputs, vectorized_keys):
    # Unfortunately, we need to check to see if the types are all the same
    # else arrow cannot make the list.
    possible_inputs = _vectorized_inputs_as_awl_non_vectorized_as_lists(
        node_inputs, vectorized_keys
    )
    running_type = None
    is_valid = True
    for v in possible_inputs.values():
        if isinstance(v.type, ArrowWeaveListType):
            obj_type = v.type.object_type
            if running_type is None:
                running_type = obj_type
            elif not running_type.assign_type(obj_type):
                is_valid = False
                break
    if is_valid:
        # TODO: If the AWL types are not all the same, it will bust here.
        op = registry_mem.memory_registry.get_op("ArrowWeaveList-vectorizedList")
        return op.lazy_call(**possible_inputs)
    else:
        return _create_manually_mapped_op(
            node_name,
            possible_inputs,
            vectorized_keys,
        )


def _vectorize_merge_special_case(node_name, node_inputs, vectorized_keys):
    self = node_inputs["lhs"]
    other = node_inputs["rhs"]

    self_ensured = preprocess_merge(self, other)
    other_ensured = preprocess_merge(other, self)

    return self_ensured.merge(other_ensured)


def vectorize(
    weave_fn,
    with_respect_to: typing.Optional[typing.Iterable[graph.VarNode]] = None,
    stack_depth: int = 0,
    strict=False,
):
    """Convert a Weave Function of T to a Weave Function of ArrowWeaveList[T]

    We walk the DAG represented by weave_fn, starting from its roots. Replace
    with_respect_to VarNodes of Type T with ArrowWeaveList[T]. Then as we
    walk up the DAG, replace OutputNodes with new op calls to whatever ops
    exist that can handle the changed input types.
    """

    # TODO: handle with_respect_to, it doesn't do anything right now.

    if stack_depth > 10:
        raise VectorizeError("Vectorize recursion depth exceeded")

    def ensure_object_constructors_created(node: graph.Node) -> graph.Node:
        if isinstance(node, graph.OutputNode):
            if node.from_op.name.startswith("objectConstructor-"):
                make_vectorized_object_constructor(node.from_op.name)
        return node

    def expand_nodes(node: graph.Node) -> graph.Node:
        if isinstance(node, graph.OutputNode):
            inputs = node.from_op.inputs
            if node.from_op.name == "number-bin":
                bin_fn = weave_internal.use(inputs["bin_fn"])
                in_ = inputs["in_"]
                return weave_internal.call_fn(bin_fn, {"row": in_})  # type: ignore
            if node.from_op.name == "timestamp-bin":
                in_ = inputs["in_"]
                res = weave_internal.better_call_fn(inputs["bin_fn"].val, in_)  # type: ignore
                return res
        return node

    def vectorize_output_node(node: graph.OutputNode, vectorized_keys: set[str]):
        # In this function, we will "vectorize" an output_node. This is a
        # shallow mapper against an output node with var nodes in its ancestry.
        # All VarNodes in the original graph will be converted to a AWL of the
        # same type. See `vectorize_along_wrt_paths` for the outer loop that
        # calls this function and performs this variable replacement.
        #
        # Moreover, we are provided a list of keys for the inputs which are in
        # the "vectorization" path. This is important bookkeeping to understand
        # if a list-like input is to be treated as a single list for each "loop"
        # of the vectorization pass (non vectorized path); or if the list-like input
        # is in the vectorization path, meaning each "loop" of the pass should "iterate"
        # over the elements. For example, consider ArrowWeaveList-vectorizedDict:
        #
        # vectorizedDict({
        #   "a": [1, 2, 3], # vectorized path
        #   "b": [4, 5, 6], # vectorized path
        # }) = [
        #   {"a": 1, "b": 4},
        #   {"a": 2, "b": 5},
        #   {"a": 3, "b": 6},
        # ]
        #
        # vectorizedDict({
        #   "a": [1, 2, 3], # vectorized path
        #   "b": [4, 5, 6], # non-vector path
        # }) = [
        #   {"a": 1, "b": [4,5,6]},
        #   {"a": 2, "b": [4,5,6]},
        #   {"a": 3, "b": [4,5,6]},
        # ]
        #
        #
        # So, the main purpose of this function is to say: given these new inputs,
        # dispatch to the correct op such that the result is properly vectorized.

        node_inputs = node.from_op.inputs
        node_name = node.from_op.name

        # First, we need to handle a a few special cases:
        # 1. If the node is a lambda function, then we know we can't vectorize it
        if _is_lambda_output_node(node):
            # Example: [[1,2,3], [3,4,5]].map(row => row.map(x => x + 1))
            return _vectorize_lambda_output_node(node, vectorized_keys)

        # 2. If the op is `dict` or `list` then we manually hard code the vectorized version
        # since dispatch will choose the non-vectorized version. Note that we transform the inputs
        # appropriately. See comments in header of function
        if node_name == "dict":
            op = registry_mem.memory_registry.get_op("ArrowWeaveList-vectorizedDict")
            return op.lazy_call(
                **_vectorized_inputs_as_awl_non_vectorized_as_lists(
                    node_inputs, vectorized_keys
                )
            )
        if node_name == "list":
            return _vectorize_list_special_case(node_name, node_inputs, vectorized_keys)

        if node_name == "merge":
            return _vectorize_merge_special_case(
                node_name, node_inputs, vectorized_keys
            )

        # 3. In the case of `Object-__getattr__`, we need to special case it will only work when the first arg is AWL
        # and the second is a string:
        if node_name == "Object-__getattr__":
            arg_names = list(node_inputs.keys())
            if arg_names[0] in vectorized_keys and arg_names[1] not in vectorized_keys:
                op = registry_mem.memory_registry.get_op(
                    "ArrowWeaveListObject-__vectorizedGetattr__"
                )
                return op.lazy_call(
                    **{
                        arg_names[0]: _ensure_list_like_node_is_awl(
                            node_inputs[arg_names[0]]
                        ),
                        arg_names[1]: node_inputs[arg_names[1]],
                    }
                )

        input0_name = list(node_inputs.keys())[0]
        input0 = list(node_inputs.values())[0]
        if input0_name in vectorized_keys and types.List(
            types.optional(types.List())
        ).assign_type(input0.type):
            if node_name.endswith("index") or node_name.endswith("__getitem__"):
                inputs_as_awl = _vectorized_inputs_as_awl(node_inputs, vectorized_keys)
                return arraylist_ops.listindex(*inputs_as_awl.values())
            elif node_name.endswith("count"):
                inputs_as_awl = _vectorized_inputs_as_awl(node_inputs, vectorized_keys)
                return arraylist_ops.list_numbers_count(*inputs_as_awl.values())
            elif node_name.endswith("max"):
                inputs_as_awl = _vectorized_inputs_as_awl(node_inputs, vectorized_keys)
                return arraylist_ops.list_numbers_max(*inputs_as_awl.values())
            elif node_name.endswith("min"):
                inputs_as_awl = _vectorized_inputs_as_awl(node_inputs, vectorized_keys)
                return arraylist_ops.list_numbers_min(*inputs_as_awl.values())
            elif node_name.endswith("avg"):
                inputs_as_awl = _vectorized_inputs_as_awl(node_inputs, vectorized_keys)
                return arraylist_ops.list_numbers_avg(*inputs_as_awl.values())
            elif node_name.endswith("sum"):
                inputs_as_awl = _vectorized_inputs_as_awl(node_inputs, vectorized_keys)
                return arraylist_ops.list_numbers_sum(*inputs_as_awl.values())

        if node_name == "dropna":
            arg_names = list(node_inputs.keys())
            if arg_names[0] in vectorized_keys:
                op = registry_mem.memory_registry.get_op(
                    "ArrowWeaveListList-vectorizedDropna"
                )
                inputs_as_awl = _vectorized_inputs_as_awl(node_inputs, vectorized_keys)
                return op.lazy_call(*inputs_as_awl.values())
        elif node_name.endswith("isNone"):
            arg_names = list(node_inputs.keys())
            if arg_names[0] in vectorized_keys:
                op = registry_mem.memory_registry.get_op(
                    "ArrowWeaveList-vectorizedIsNone"
                )
                inputs_as_awl = _vectorized_inputs_as_awl(node_inputs, vectorized_keys)
                return op.lazy_call(*inputs_as_awl.values())
        elif node_name.endswith("-equal") or node_name.endswith("-notEqual"):
            # if the first arg is not in the vectorized path, but is a constant, and the second is in the vectorized path,
            # then we swap the order of the inputs so that we can use existing ops we have written where the AWL is first
            # in order for tag flow to proceed as expected
            arg_names = list(node_inputs.keys())
            if arg_names[1] in vectorized_keys and arg_names[0] not in vectorized_keys:
                inputs_as_awl = _vectorized_inputs_as_awl(node_inputs, vectorized_keys)
                inputs_as_awl = {
                    arg_names[0]: inputs_as_awl[arg_names[1]],
                    arg_names[1]: inputs_as_awl[arg_names[0]],
                }
                maybe_op = _safe_get_op_for_inputs(node_name, inputs_as_awl)
                if maybe_op is not None:
                    return maybe_op.lazy_call(*inputs_as_awl.values())

        # 4. Non SIMD ops (List/AWL)
        if _is_non_simd_node(node, vectorized_keys):
            return _create_manually_mapped_op(
                node.from_op.name,
                node_inputs,
                vectorized_keys,
            )

        # Now, if we have not returned by now, then we can move on to the main logic of this function.

        # Part 1: Attempt to dispatch using the AWL inputs (This would be the most ideal case - pure AWL)
        inputs_as_awl = _vectorized_inputs_as_awl(node_inputs, vectorized_keys)
        maybe_op = _safe_get_op_for_inputs(node_name, inputs_as_awl)
        if maybe_op is not None:
            return maybe_op.lazy_call(*inputs_as_awl.values())

        # Part 2: We still want to use Arrow if possible. Here we are going to attempt to
        # weavify, then vectorize the op implementation.
        node_op = registry_mem.memory_registry.get_op(node_name)
        maybe_weavified_op = _safe_get_weavified_op(node_op)
        if maybe_weavified_op is not None:
            with_respect_to = None  # TODO: only vectorize the vectorization path!
            vectorized = vectorize(
                maybe_weavified_op, with_respect_to, stack_depth=stack_depth + 1
            )
            return weave_internal.call_fn(vectorized, inputs_as_awl)

        # Part 3: Attempt to dispatch using the list-like inputs (this is preferred to the final case)
        inputs_as_list = _vectorized_inputs_as_list(node_inputs, vectorized_keys)
        maybe_op = _safe_get_op_for_inputs(node_name, inputs_as_list)
        if maybe_op is not None and maybe_op.derived_from is None:
            return maybe_op.lazy_call(*inputs_as_list.values())

        # Mapped ops can be handled with map_each
        if node_op.derived_from is not None:
            # TODO: other arguments may also be vectorized. In that case this will crash
            input_vals = list(node_inputs.values())
            map_each_op = registry_mem.memory_registry.get_op("ArrowWeaveList-mapEach")
            return map_each_op(
                input_vals[0], lambda x: node_op.derived_from(x, *input_vals[1:])
            )
        # If an op is already an arrow version, we may still need to use mapeach
        # to lift it to another dimension. This needs to be generalized I think.
        # Added for now for timeseries plot.
        if node_op.name == "ArrowWeaveListTypedDict-pick":
            input_vals = list(node_inputs.values())
            map_each_op = registry_mem.memory_registry.get_op("ArrowWeaveList-mapEach")
            pick_op = registry_mem.memory_registry.get_op("typedDict-pick")
            return map_each_op(input_vals[0], lambda x: pick_op(x, *input_vals[1:]))

        if strict:
            raise errors.WeaveVectorizationError(f"Could not vectorize op {node_name}")
        else:
            # Final Fallback: We have no choice anymore. We must bail out completely to mapping
            # over all the vectorized inputs and calling the function directly.
            # If we hit this, then it means our vectorization has
            # created inputs which have no matching op. For example,
            # if we are doing a pick operation and the key is a
            # vectorized VarNode. This happens when picking a run
            # color using a vectorized list of runs for a table
            # (since pick(dict, list<string>) is not implemented).
            # This can happen for other ops like `add` and `mul` as
            # well (imagine `row => 1 + row`)
            #
            # In order to safely handle this case, we need to simply map
            # the original op over all the vectorized inputs.
            res = _create_manually_mapped_op(
                node_name,
                node_inputs,
                vectorized_keys,
            )
            message = (
                f"Encountered non-dispatchable op ({node_name}) during vectorization."
            )
            message += "This is likely due to vectorization path of the function not leading to the"
            message += "first parameter. Bailing out to manual mapping"
            logging.warning(message)
            return res

    # Vectorize is "with respect to" (wrt) specific variable nodes in the graph.
    # vectorize_along_wrt_paths keeps track of nodes that have already
    # been vectorized, ie nodes that have a wrt variable in their ancestry.
    # We don't try to vectorize paths for which that is not the case.
    already_vectorized_nodes: set[graph.Node] = set()

    def vectorize_along_wrt_paths(node: graph.Node):
        if isinstance(node, graph.OutputNode):
            vectorized_keys = set()
            for input_key, input_node in node.from_op.inputs.items():
                if input_node in already_vectorized_nodes:
                    vectorized_keys.add(input_key)
            if len(vectorized_keys) == 0:
                # not along vectorize path
                return node
            new_node = vectorize_output_node(node, vectorized_keys)
            already_vectorized_nodes.add(new_node)
            return new_node
        elif isinstance(node, graph.VarNode):
            # Vectorize variable
            if with_respect_to is None or any(
                node is wrt_node for wrt_node in with_respect_to
            ):
                new_node = graph.VarNode(ArrowWeaveListType(node.type), node.name)
                already_vectorized_nodes.add(new_node)
                return new_node
            # not along vectorize path
            return node
        elif isinstance(node, graph.ConstNode):
            # not along vectorize path
            return node
        else:
            raise errors.WeaveInternalError("Unexpected node: %s" % node)

    weave_fn = graph.map_nodes_top_level(
        [weave_fn], ensure_object_constructors_created
    )[0]
    weave_fn = graph.map_nodes_top_level([weave_fn], expand_nodes)[0]
    return graph.map_nodes_top_level([weave_fn], vectorize_along_wrt_paths)[0]


def _call_and_ensure_awl(
    awl: ArrowWeaveList, called: graph.OutputNode
) -> ArrowWeaveList:
    from .. import compile

    with compile.disable_compile():
        res = use(called)
    # Since it is possible that the result of `use` bails out of arrow due to a
    # mismatch in the types / op support. This is most likely due to gap in the
    # implementation of vectorized ops. However, there are cases where it is
    # currently expected - for example calling a custom op on a custom type. An
    # example of this is in `ops_arrow/test_arrow.py::test_custom_types_tagged`:
    #
    #     ` data_node.map(lambda row: row["im"].width_())`
    #
    # If such cases did not exist, then we should probably raise in this case.
    # However, for now, we will just convert the result back to arrow if it is a
    # list.
    if not isinstance(res, ArrowWeaveList):
        err_msg = f"Applying vectorized function {called} to awl of {awl.object_type} \
            resulted in a non vectorized result type: {type(res)}. This likely \
            means 1 or more ops in the function were converted to the list \
            implementation in compile."
        if isinstance(res, list):
            res = convert.to_arrow(res)
            logging.warning(err_msg)
        else:
            raise errors.WeaveVectorizationError(err_msg)

    return res


def _call_vectorized_fn_node_maybe_awl(
    awl: ArrowWeaveList, vectorized_fn: graph.OutputNode
) -> graph.OutputNode:
    index_awl: ArrowWeaveList[int] = ArrowWeaveList(pa.array(np.arange(len(awl))))
    row_type = ArrowWeaveListType(awl.object_type)
    try:
        fn_res_node = weave_internal.call_fn(
            vectorized_fn,
            {
                "row": weave_internal.make_const_node(row_type, awl),
                "index": weave_internal.make_const_node(
                    ArrowWeaveListType(types.Int()), index_awl
                ),
            },
        )
    except errors.WeaveMissingVariableError as e:
        raise errors.WeaveBadRequest('Invalid variable "%s" in function' % e.args[0])
    return typing.cast(graph.OutputNode, weave_internal.refine_graph(fn_res_node))


def _apply_fn_node_with_tag_pushdown(
    awl: ArrowWeaveList, fn: graph.OutputNode
) -> ArrowWeaveList:
    tagged_awl = pushdown_list_tags(awl)
    return _apply_fn_node(tagged_awl, fn)


def _ensure_variadic_fn(
    fn: graph.OutputNode, dummy_var_type: types.Type, dummy_var_name: str = "row"
) -> graph.OutputNode:
    # Check if fn contains variables.
    contains_vars = len(graph.expr_vars(fn)) > 0
    # if it does, return early.
    if contains_vars:
        return fn
    # else, create a new graph which contains a row
    # variable. We will use a dict followed by a pick.
    return dict_(a=fn, b=graph.VarNode(dummy_var_type, dummy_var_name))["a"]


def _apply_fn_node(awl: ArrowWeaveList, fn: graph.OutputNode) -> ArrowWeaveList:
    debug_str = graph_debug.node_expr_str_full(fn)
    logging.info("Vectorizing: %s", debug_str)
    from .. import execute_fast

    fn = execute_fast._resolve_static_branches(fn)
    logging.info("Vectorizing. Static branch resolution complete.: %s", debug_str)

    vecced = vectorize(_ensure_variadic_fn(fn, awl.object_type))
    debug_str = graph_debug.node_expr_str_full(vecced)
    logging.info("Vectorizing. Vectorized: %s", debug_str)
    called = _call_vectorized_fn_node_maybe_awl(awl, vecced)
    return _call_and_ensure_awl(awl, called)
