# Deserialize and serialize have to match the javascript implementation, which
# needlessly adds an entry for nodes and ops. It'd be simpler to just encode
# nodes and inline the ops in their respective output nodes.

import typing

from . import graph
from . import weave_types as types


NodeOrOp = typing.Union[graph.Node, graph.Op]

# TODO(dg): Replace Any
SerializedNode = typing.Any
MapNodeOrOpToSerialized = typing.Dict[NodeOrOp, typing.Tuple[SerializedNode, int]]


class SerializedReturnType(typing.TypedDict):
    nodes: typing.List[SerializedNode]
    rootNodes: typing.List[int]


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
            serialized_nodes[node] = (node.to_json(), node_id)
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
    root_nodes = [_serialize_node(n, serialized) for n in graphs]
    nodes = list(range(len(serialized)))
    for node_json, node_id in serialized.values():
        nodes[node_id] = node_json
    return {"nodes": nodes, "rootNodes": root_nodes}


def _deserialize_node(
    index: int,
    nodes: typing.List[SerializedNode],
    parsed_nodes: typing.MutableMapping[int, graph.Node],
) -> graph.Node:
    if index in parsed_nodes:
        return parsed_nodes[index]
    node = nodes[index]

    parsed_node: graph.Node
    if node["nodeType"] == "const":
        if isinstance(node["type"], dict) and node["type"]["type"] == "function":
            print("PARSE CONST FUNCTION", node)
            op = nodes[node["val"]["fromOp"]]
            params = {}
            for param_name, param_node_index in op["inputs"].items():
                params[param_name] = _deserialize_node(
                    param_node_index, nodes, parsed_nodes
                )
            parsed_node = graph.ConstNode(
                types.TypeRegistry.type_from_dict(node["type"]),
                graph.OutputNode(
                    # TODO!!!! What does the javascript client do here? It sends a blank type :(
                    types.Any(),
                    op["name"],
                    params,
                ),
            )
        else:
            parsed_node = graph.ConstNode.from_json(node)
    elif node["nodeType"] == "output":
        op = nodes[node["fromOp"]]
        params = {}
        for param_name, param_node_index in op["inputs"].items():
            params[param_name] = _deserialize_node(
                param_node_index, nodes, parsed_nodes
            )
        parsed_node = graph.OutputNode(
            types.TypeRegistry.type_from_dict(node["type"]), op["name"], params
        )
    elif node["nodeType"] == "var":
        parsed_node = graph.VarNode.from_json(node)
    parsed_nodes[index] = parsed_node
    return parsed_node


def deserialize(serialized: SerializedReturnType) -> "list[graph.Node]":
    # For some reason what javascript sends isn't guaranteed to be sorted
    # along the graph topology. If it were we could do an easy linear
    # implementation. But its not so we recurse for now.
    nodes = serialized["nodes"]
    root_nodes = serialized["rootNodes"]
    parsed_nodes: dict[int, graph.Node] = {}

    return [_deserialize_node(i, nodes, parsed_nodes) for i in root_nodes]
