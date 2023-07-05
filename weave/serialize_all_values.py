# This is the same as serialize.py, with a few differences:
# 1. Handles the new serialized format, which transforms every value into a reference.
# 2. Instead of resolving serialized refs and parsing them in one go, we first replace all refs
#    with their respective values, then parse the resulting nested structure.
# 3. We use an instantiated type cache so that we don't spend cycles instantiating duplicate types.
#    This greatly improves performance when deserializing large graphs with many duplicate types.

from typing import Any, Dict, Tuple, Union, TypedDict, MutableMapping
import hashlib
import json
import random

from . import value_or_error

from . import graph
from . import weave_types as types
from . import errors
from . import weave_internal
from . import storage
from . import memo

NodeOrOp = Union[graph.Node, graph.Op]

# TODO(dg): Replace Any
SerializedNode = Any
MapNodeOrOpToSerialized = Dict[NodeOrOp, Tuple[SerializedNode, int]]


class SerializedReturnType(TypedDict):
    nodes: list[SerializedNode]
    targetNodes: list[int]


def deserialize_all_values(
    serialized: SerializedReturnType,
) -> value_or_error.ValueOrErrors[graph.Node]:
    nodes = serialized["nodes"]
    target_nodes = serialized["targetNodes"]

    deserialized_values: dict[int, Any] = {}
    deserialized_target_nodes = list(
        map(lambda i: _deserialize_value(nodes, deserialized_values, i), target_nodes)
    )

    parsed_nodes: dict[int, graph.Node] = {}
    # WeaveJS does not do a good job deduplicating nodes currently, so we do it here.
    # This ensures we don't execute the same node many times.
    hashed_nodes: dict[str, graph.Node] = {}

    deserialized_target_node_values = value_or_error.ValueOrErrors.from_values(
        deserialized_target_nodes
    )

    with memo.memo_storage():
        with types.type_from_dict_cache():
            return deserialized_target_node_values.safe_map(
                lambda node: _parse_node(node, parsed_nodes, hashed_nodes)
            )


def _deserialize_value(
    nodes: list[SerializedNode], deserialized_values: dict[int, Any], i: int
) -> Any:
    if i in deserialized_values:
        return deserialized_values[i]

    v = nodes[i]

    if not isinstance(v, list) and not isinstance(v, dict):
        deserialized_values[i] = v
        return v
    if isinstance(v, list):
        arr = [_deserialize_value(nodes, deserialized_values, i) for i in v]
        deserialized_values[i] = arr
        return arr
    if isinstance(v, dict):
        dct = {
            k: _deserialize_value(nodes, deserialized_values, i) for k, i in v.items()
        }
        deserialized_values[i] = dct
        return dct


def _parse_node(
    node_dict: Any,
    parsed_nodes: MutableMapping[int, graph.Node],
    hashed_nodes: MutableMapping[str, graph.Node],
) -> graph.Node:
    # Return memoized result if available
    if id(node_dict) in parsed_nodes:
        return parsed_nodes[id(node_dict)]

    # Parse node according to its type
    parsed_node: graph.Node
    if node_dict["nodeType"] == "const":
        parsed_node = _parse_const_node(node_dict, parsed_nodes, hashed_nodes)
    elif node_dict["nodeType"] == "output":
        parsed_node = _parse_output_node(node_dict, parsed_nodes, hashed_nodes)
    elif node_dict["nodeType"] == "var":
        parsed_node = _parse_var_node(node_dict)
    else:
        raise errors.WeaveInternalError("invalid node type encountered while parsing")

    # Ensure we don't have duplicate nodes.
    # If another node has been parsed with the same id, use that one instead.
    id_ = node_id(parsed_node)
    if id_ in hashed_nodes:
        parsed_node = hashed_nodes[id_]
    else:
        hashed_nodes[id_] = parsed_node

    # Memoize result
    parsed_nodes[id(node_dict)] = parsed_node

    return parsed_node


def _parse_const_node(
    node_dict: Any,
    parsed_nodes: MutableMapping[int, graph.Node],
    hashed_nodes: MutableMapping[str, graph.Node],
) -> graph.Node:
    is_function_node = (
        isinstance(node_dict["type"], dict) and node_dict["type"]["type"] == "function"
    )

    if not is_function_node:
        return graph.ConstNode.from_json(node_dict)

    # Parse function node body according to its type
    fn_body_node_dict = node_dict["val"]
    parsed_fn_body_node: graph.Node
    if fn_body_node_dict["nodeType"] == "var":
        parsed_fn_body_node = _parse_fn_body_var_node(fn_body_node_dict)
    elif fn_body_node_dict["nodeType"] == "const":
        parsed_fn_body_node = _parse_fn_body_const_node(fn_body_node_dict)
    elif fn_body_node_dict["nodeType"] == "output":
        parsed_fn_body_node = _parse_fn_body_output_node(
            node_dict, fn_body_node_dict, parsed_nodes, hashed_nodes
        )
    else:
        raise errors.WeaveInternalError(
            "invalid function node encountered in deserialize"
        )
    return graph.ConstNode(
        types.TypeRegistry.type_from_dict_use_cache(node_dict["type"]),
        parsed_fn_body_node,
    )


def _parse_fn_body_var_node(fn_body_node_dict: Any) -> graph.VarNode:
    return weave_internal.make_var_node(
        types.TypeRegistry.type_from_dict_use_cache(fn_body_node_dict["type"]),
        fn_body_node_dict["varName"],
    )


def _parse_fn_body_const_node(fn_body_node_dict: Any) -> graph.ConstNode:
    fn_body_const_val = fn_body_node_dict["val"]
    if isinstance(fn_body_const_val, dict) and "nodeType" in fn_body_const_val:
        # This case happens when we have a quoted function.
        fn_body_const_val = graph.Node.node_from_json(fn_body_const_val)
    return weave_internal.make_const_node(
        types.TypeRegistry.type_from_dict_use_cache(fn_body_node_dict["type"]),
        fn_body_const_val,
    )


def _parse_fn_body_output_node(
    node_dict: Any,
    fn_body_node_dict: Any,
    parsed_nodes: MutableMapping[int, graph.Node],
    hashed_nodes: MutableMapping[str, graph.Node],
) -> graph.OutputNode:
    op = fn_body_node_dict["fromOp"]
    params = {}
    for param_name, param_value in op["inputs"].items():
        params[param_name] = _parse_node(param_value, parsed_nodes, hashed_nodes)
    node_type = types.TypeRegistry.type_from_dict_use_cache(node_dict["type"])
    if not isinstance(node_type, types.Function):
        raise errors.WeaveInternalError("expected function type, got %s" % node_type)
    return weave_internal.make_output_node(
        node_type.output_type,
        op["name"],
        params,
    )


def _parse_output_node(
    node_dict: Any,
    parsed_nodes: MutableMapping[int, graph.Node],
    hashed_nodes: MutableMapping[str, graph.Node],
) -> graph.OutputNode:
    op = node_dict["fromOp"]
    params = {}
    for param_name, param_value in op["inputs"].items():
        params[param_name] = _parse_node(param_value, parsed_nodes, hashed_nodes)
    return graph.OutputNode(
        types.TypeRegistry.type_from_dict_use_cache(node_dict["type"]),
        op["name"],
        params,
    )


def _parse_var_node(node_dict: Any) -> graph.VarNode:
    return graph.VarNode.from_json(node_dict)


@memo.memo
def node_id(node: graph.Node) -> str:
    hashable = {"type": node.type.to_dict()}
    if isinstance(node, graph.OutputNode):
        hashable["op_name"] = node.from_op.name
        hashable["inputs"] = {
            arg_name: node_id(arg_node)
            if not _is_lambda(arg_node)
            else json.dumps(arg_node.to_json())
            for arg_name, arg_node in node.from_op.inputs.items()
        }
    elif isinstance(node, graph.VarNode):
        # Ensure we don't share var nodes. That's invalid!
        hashable["name"] = str(random.random())
    elif isinstance(node, graph.ConstNode):
        if isinstance(node.val, graph.OutputNode) or isinstance(
            node.val, graph.VarNode
        ):
            # Ensure we don't share function nodes. That's invalid!
            hashable["val"] = str(random.random())
        else:
            hashable["val"] = storage.to_python(node.val)
    else:
        raise errors.WeaveInternalError("invalid node encountered: %s" % node)
    hash = hashlib.md5()
    hash.update(json.dumps(hashable).encode())
    return hash.hexdigest()


def _is_lambda(node: graph.Node) -> bool:
    return isinstance(node, graph.ConstNode) and (
        isinstance(node.val, graph.OutputNode) or isinstance(node.val, graph.VarNode)
    )
