"""Fixes for compatibility with WeaveJS

TODO: this file is not complete. We should try to put all compability fixes here.
    Grep for "js_compat" to find other instances.
"""
import typing
import copy

from . import weave_types
from . import graph
from . import weave_types
from . import errors


def _convert_specific_opname_to_generic_opname(
    name: str, inputs: dict[str, typing.Any]
) -> tuple[str, dict[str, typing.Any]]:
    if name == "typedDict-pick" or name == "dict-pick" or name == "list-pick":
        return "pick", {"obj": inputs["self"], "key": inputs["key"]}
    elif name == "groupresult-map":
        return "map", {"arr": inputs["self"], "mapFn": inputs["map_fn"]}
    elif name == "groupresult-groupby":
        return "groupby", {"arr": inputs["self"], "groupByFn": inputs["group_fn"]}
    elif name == "groupresult-count" or name == "projectArtifactVersions-count":
        return "count", {"arr": inputs["self"]}
    elif name == "groupresult-key":
        return "group-groupkey", {"obj": inputs["self"]}
    elif name == "list-map":
        return "map", {"arr": inputs["self"], "mapFn": inputs["map_fn"]}
    elif name == "list-groupby":
        return "groupby", {"arr": inputs["self"], "groupByFn": inputs["group_by_fn"]}
    elif name == "list-filter":
        return "filter", {"arr": inputs["self"], "filterFn": inputs["filter_fn"]}
    elif name == "list-__getitem__":
        return "index", {"arr": inputs["arr"], "index": inputs["index"]}
    elif (
        name == "groupresult-__getitem__"
        or name == "artifacts-__getitem__"
        or name == "projectArtifactVersions-__getitem__"
    ):
        return "index", {"arr": inputs["self"], "index": inputs["index"]}
    return name, inputs


def convert_specific_opname_to_generic_opname(
    name: str, inputs: dict[str, typing.Any]
) -> tuple[str, dict[str, typing.Any]]:
    if name.startswith("mapped_"):
        unmapped_name = name[7:]
        res = _convert_specific_opname_to_generic_opname(unmapped_name, inputs)
        if res[0] == unmapped_name:
            raise errors.WeaveInternalError("Unable to fix up op: " + name)
        return res
    return _convert_specific_opname_to_generic_opname(name, inputs)


def convert_specific_ops_to_generic_ops_node(node: graph.Node) -> graph.Node:
    """Converts specific ops like typedDict-pick to generic ops like pick"""

    def convert_specific_op_to_generic_op(node: graph.Node):
        if isinstance(node, graph.ConstNode) and isinstance(
            node.type, weave_types.Function
        ):
            return graph.ConstNode(
                node.type, convert_specific_ops_to_generic_ops_node(node.val)
            )
        if not isinstance(node, graph.OutputNode):
            return node
        name, inputs = convert_specific_opname_to_generic_opname(
            node.from_op.name, node.from_op.inputs
        )
        return graph.OutputNode(node.type, name, inputs)

    return graph.map_nodes_full([node], convert_specific_op_to_generic_op)[0]


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
            graph.op_full_name(node.from_op),
            node.from_op.inputs,
        )

    return graph.map_nodes_full([node], remove_op_version)[0]


def remove_opcall_versions_data(data):
    """Fix op call names for serialized objects containing graphs"""
    if isinstance(data, list):
        return [remove_opcall_versions_data(d) for d in data]
    elif isinstance(data, dict):
        d = data
        if "name" in data and isinstance(data["name"], str) and ":" in data["name"]:
            d = copy.copy(data)
            d["name"] = graph.opuri_full_name(data["name"])
        return {k: remove_opcall_versions_data(v) for k, v in d.items()}
    return data


def fixup_node(node: graph.Node) -> graph.Node:
    node = remove_opcall_versions_node(node)
    return convert_specific_ops_to_generic_ops_node(node)


def fixup_data(data):
    data = remove_opcall_versions_data(data)
    return convert_specific_ops_to_generic_ops_data(data)
