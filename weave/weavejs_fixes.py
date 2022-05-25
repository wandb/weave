"""Fixes for compatibility with WeaveJS

TODO: this file is not complete. We should try to put all compability fixes here.
    Grep for "js_compat" to find other instances.
"""
import typing
import copy
from . import graph


def convert_specific_opname_to_generic_opname(
    name: str, inputs: dict[str, typing.Any]
) -> tuple[str, dict[str, typing.Any]]:
    if name == "typedDict-pick" or name == "dict-pick":
        return "pick", {"obj": inputs["self"], "key": inputs["key"]}
    elif name == "groupresult-map":
        return "map", {"arr": inputs["self"], "mapFn": inputs["map_fn"]}
    elif name == "groupresult-groupby":
        return "groupby", {"arr": inputs["self"], "groupByFn": inputs["group_fn"]}
    elif name == "groupresult-count" or name == "projectArtifactVersions-count":
        return "count", {"arr": inputs["self"]}
    elif name == "groupresult-key":
        return "group-groupkey", {"obj": inputs["self"]}
    elif (
        name == "list-__getitem__"
        or name == "groupresult-__getitem__"
        or name == "artifacts-__getitem__"
        or name == "projectArtifactVersions-__getitem__"
    ):
        return "index", {"arr": inputs["self"], "index": inputs["index"]}
    return name, inputs


def convert_specific_ops_to_generic_ops_node(node: graph.Node) -> graph.Node:
    """Converts specific ops like typedDict-pick to generic ops like pick"""

    def convert_specific_op_to_generic_op(node: graph.Node):
        if not isinstance(node, graph.OutputNode):
            return node
        name, inputs = convert_specific_opname_to_generic_opname(
            node.from_op.name, node.from_op.inputs
        )
        return graph.OutputNode(node.type, name, inputs)

    return graph.map_nodes(node, convert_specific_op_to_generic_op)


def convert_specific_ops_to_generic_ops_data(data):
    """Fix op call names for serialized objects containing graphs"""
    if isinstance(data, list):
        return [convert_specific_ops_to_generic_ops_data(d) for d in data]
    elif isinstance(data, dict):
        d = data
        if "name" in data and "inputs" in data:
            d["name"], d["inputs"] = convert_specific_opname_to_generic_opname(
                d["name"], d["inputs"]
            )
        return {k: convert_specific_ops_to_generic_ops_data(v) for k, v in d.items()}
    return data


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


def fixup_node(node: graph.Node) -> graph.Node:
    node = remove_opcall_versions_node(node)
    return convert_specific_ops_to_generic_ops_node(node)


def fixup_data(data):
    data = remove_opcall_versions_data(data)
    return convert_specific_ops_to_generic_ops_data(data)


def unwrap_tag_type(serialized_type):
    if isinstance(serialized_type, dict) and serialized_type.get("type") == "tagged":
        return serialized_type["value"]
    return serialized_type
