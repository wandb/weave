"""Fixes for compatibility with WeaveJS

TODO: this file is not complete. We should try to put all compability fixes here.
    Grep for "js_compat" to find other instances.
"""
import copy
from . import graph


def remove_opcall_versions_node(node: graph.Node) -> graph.Node:
    """Fix op call names"""

    def remove_op_version(node: graph.Node):
        if not isinstance(node, graph.OutputNode):
            return node
        return graph.OutputNode(
            node.type,
            graph.opname_without_version(node.from_op),
            node.from_op.inputs,
        )

    return graph.map_nodes(node, remove_op_version)


def remove_opcall_versions_data(data):
    """Fix op call names for serialized objects containing graphs"""
    if isinstance(data, list):
        return [remove_opcall_versions_data(d) for d in data]
    elif isinstance(data, dict):
        d = data
        if "name" in data and ":" in data["name"]:
            d = copy.copy(data)
            d["name"] = data["name"].split(":")[0]
        return {k: remove_opcall_versions_data(v) for k, v in d.items()}
    return data
