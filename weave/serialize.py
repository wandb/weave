# Deserialize and serialize have to match the javascript implementation, which
# needlessly adds an entry for nodes and ops. It'd be simpler to just encode
# nodes and inline the ops in their respective output nodes.

import typing
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


NodeOrOp = typing.Union[graph.Node, graph.Op]

# TODO(dg): Replace Any
SerializedNode = typing.Any
MapNodeOrOpToSerialized = typing.Dict[NodeOrOp, typing.Tuple[SerializedNode, int]]


class SerializedReturnType(typing.TypedDict):
    nodes: typing.List[SerializedNode]
    targetNodes: typing.List[int]


def _serialize_node(node: NodeOrOp, serialized_nodes: MapNodeOrOpToSerialized) -> int:
    if node in serialized_nodes:
        return serialized_nodes[node][1]

    if isinstance(node, graph.Op):
        param_indexes = {}
        for param_name, param_node in node.inputs.items():
            param_indexes[param_name] = _serialize_node(param_node, serialized_nodes)
        op_id = len(serialized_nodes)
        serialized_nodes[node] = ({"name": node.name, "inputs": param_indexes}, op_id)
        return op_id
    if isinstance(node, graph.ConstNode):
        if isinstance(node.type, types.Function):
            op_id = _serialize_node(node.val.from_op, serialized_nodes)
            node_id = len(serialized_nodes)
            serialized_nodes[node] = (
                {
                    "nodeType": "const",
                    "type": node.type.to_dict(),
                    "val": {"nodeType": "output", "fromOp": op_id},
                },
                node_id,
            )
            return node_id
        else:
            node_id = len(serialized_nodes)
            serialized_nodes[node] = (
                node.to_json(),
                node_id,
            )
            return node_id
    elif isinstance(node, graph.OutputNode):
        op_id = _serialize_node(node.from_op, serialized_nodes)
        node_id = len(serialized_nodes)
        serialized_nodes[node] = (
            {"nodeType": "output", "type": node.type.to_dict(), "fromOp": op_id},
            node_id,
        )
        return node_id
    elif isinstance(node, graph.VarNode):
        node_id = len(serialized_nodes)
        serialized_nodes[node] = (node.to_json(), node_id)
        return node_id

    raise ValueError(f"Could not serialize node: {node}")


def serialize(graphs: typing.List[graph.Node]) -> SerializedReturnType:
    serialized: MapNodeOrOpToSerialized = {}
    target_nodes = [_serialize_node(n, serialized) for n in graphs]
    nodes = list(range(len(serialized)))
    for node_json, node_id in serialized.values():
        nodes[node_id] = node_json
    return {"nodes": nodes, "targetNodes": target_nodes}


def _is_lambda(node: graph.Node):
    return isinstance(node, graph.ConstNode) and (
        isinstance(node.val, graph.OutputNode) or isinstance(node.val, graph.VarNode)
    )


@memo.memo
def node_id(node: graph.Node):
    hashable: dict[str, typing.Any] = {}
    if isinstance(node, graph.OutputNode):
        hashable["op_name"] = node.from_op.name
        hashable["inputs"] = {
            arg_name: node_id(arg_node)
            for arg_name, arg_node in node.from_op.inputs.items()
        }
    elif isinstance(node, graph.VarNode):
        # Must include type here, Const and OutputNode types can
        # be inferred from the graph, but VarNode types cannot.
        hashable["type"] = node.type.to_dict()
        hashable["name"] = node.name
    elif isinstance(node, graph.ConstNode):
        if isinstance(node.val, graph.OutputNode) or isinstance(
            node.val, graph.VarNode
        ):
            hashable["val"] = {"lambda": True, "body": node_id(node.val)}
        else:
            hashable["val"] = storage.to_python(node.val)
        hashable["type"] = storage.to_python(node.type)
    else:
        raise errors.WeaveInternalError("invalid node encountered: %s" % node)
    hash = hashlib.md5()
    hash.update(json.dumps(hashable).encode())
    return hash.hexdigest()


def _deserialize_node(
    index: int,
    nodes: typing.List[SerializedNode],
    parsed_nodes: typing.MutableMapping[int, graph.Node],
    hashed_nodes: typing.MutableMapping[str, graph.Node],
) -> graph.Node:
    if index in parsed_nodes:
        return parsed_nodes[index]
    node = nodes[index]

    parsed_node: graph.Node
    if node["nodeType"] == "const":
        if isinstance(node["type"], dict) and node["type"]["type"] == "function":
            fn_body_node = node["val"]
            parsed_fn_body_node: graph.Node
            if fn_body_node["nodeType"] == "var":
                parsed_fn_body_node = weave_internal.make_var_node(
                    types.TypeRegistry.type_from_dict(fn_body_node["type"]),
                    fn_body_node["varName"],
                )
            elif fn_body_node["nodeType"] == "const":
                fn_body_const_val = fn_body_node["val"]
                if (
                    isinstance(fn_body_const_val, dict)
                    and "nodeType" in fn_body_const_val
                ):
                    # This case happens when we have a quoted function.
                    fn_body_const_val = graph.Node.node_from_json(fn_body_const_val)
                parsed_fn_body_node = weave_internal.make_const_node(
                    types.TypeRegistry.type_from_dict(fn_body_node["type"]),
                    fn_body_const_val,
                )
            elif fn_body_node["nodeType"] == "output":
                op = nodes[fn_body_node["fromOp"]]
                params = {}
                for param_name, param_node_index in op["inputs"].items():
                    params[param_name] = _deserialize_node(
                        param_node_index, nodes, parsed_nodes, hashed_nodes
                    )
                node_type = types.TypeRegistry.type_from_dict(node["type"])
                if not isinstance(node_type, types.Function):
                    raise errors.WeaveInternalError(
                        "expected function type, got %s" % node_type
                    )
                parsed_fn_body_node = weave_internal.make_output_node(
                    node_type.output_type,
                    op["name"],
                    params,
                )
            else:
                raise errors.WeaveInternalError(
                    "invalid function node encountered in deserialize"
                )
            parsed_node = graph.ConstNode(
                types.TypeRegistry.type_from_dict(node["type"]), parsed_fn_body_node
            )
        else:
            parsed_node = graph.ConstNode.from_json(node)
    elif node["nodeType"] == "output":
        op = nodes[node["fromOp"]]
        params = {}
        for param_name, param_node_index in op["inputs"].items():
            params[param_name] = _deserialize_node(
                param_node_index, nodes, parsed_nodes, hashed_nodes
            )
        parsed_node = graph.OutputNode(
            types.TypeRegistry.type_from_dict(node["type"]), op["name"], params
        )
    elif node["nodeType"] == "var":
        parsed_node = graph.VarNode.from_json(node)
    id_ = node_id(parsed_node)
    if id_ in hashed_nodes:
        parsed_node = hashed_nodes[id_]
    else:
        hashed_nodes[id_] = parsed_node
    parsed_nodes[index] = parsed_node
    return parsed_node


def deserialize(
    serialized: SerializedReturnType,
) -> value_or_error.ValueOrErrors[graph.Node]:
    # For some reason what javascript sends isn't guaranteed to be sorted
    # along the graph topology. If it were we could do an easy linear
    # implementation. But its not so we recurse for now.
    nodes = serialized["nodes"]
    target_nodes = serialized.get("targetNodes")
    if target_nodes is None:
        # Handle old format for backward compat with request replay datasets.
        target_nodes = serialized["rootNodes"]  # type: ignore

    parsed_nodes: dict[int, graph.Node] = {}
    # WeaveJS does not do a good job deduplicating nodes currently, so we do it here.
    # This ensures we don't execute the same node many times.
    hashed_nodes: dict[str, graph.Node] = {}

    target_node_values = value_or_error.ValueOrErrors.from_values(target_nodes)

    with memo.memo_storage():
        return target_node_values.safe_map(
            lambda i: _deserialize_node(i, nodes, parsed_nodes, hashed_nodes)
        )
