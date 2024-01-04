"""Fixes for compatibility with WeaveJS

TODO: this file is not complete. We should try to put all compability fixes here.
    Grep for "js_compat" to find other instances.
"""
import typing
import copy
import math

from . import weave_types
from . import graph
from . import weave_types
from . import errors


def _convert_specific_opname_to_generic_opname(
    name: str, inputs: dict[str, typing.Any]
) -> tuple[str, dict[str, typing.Any]]:
    if (
        name == "typedDict-pick"
        or name == "dict-pick"
        or name == "list-pick"
        or name == "ArrowWeaveListTypedDict-pick"
    ):
        return "pick", {"obj": inputs["self"], "key": inputs["key"]}
    elif name == "ArrowWeaveList-concat":
        return "concat", {"arr": inputs["arr"]}
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
    elif name == "list-filter" or name == "ArrowWeaveList-filter":
        return "filter", {"arr": inputs["self"], "filterFn": inputs["filter_fn"]}
    elif name == "list-__getitem__":
        return "index", {"arr": inputs["arr"], "index": inputs["index"]}
    elif name == "ArrowWeaveList-limit":
        return "limit", {"arr": inputs["self"], "limit": inputs["limit"]}
    elif name == "ArrowWeaveList-map":
        return "map", {"arr": inputs["self"], "mapFn": inputs["map_fn"]}
    elif name == "ArrowWeaveListString-equal":
        return "number-equal", {"lhs": inputs["self"], "rhs": inputs["other"]}
    elif name == "ArrowWeaveListNumber-mult":
        return "number-mult", {"lhs": inputs["self"], "rhs": inputs["other"]}
    elif name == "ArrowWeaveListNumber-add":
        return "number-add", {"lhs": inputs["self"], "rhs": inputs["other"]}
    elif name == "ArrowWeaveListNumber-min":
        return "numbers-min", {"numbers": inputs["self"]}
    elif name == "ArrowWeaveListNumber-max":
        return "numbers-max", {"numbers": inputs["self"]}
    elif name == "ArrowWeaveListNumber-sum":
        return "numbers-sum", {"numbers": inputs["self"]}
    elif name == "ArrowWeaveListNumber-avg":
        return "numbers-avg", {"numbers": inputs["self"]}
    elif name == "ArrowWeaveListDate-min":
        return "dates-min", {"dates": inputs["self"]}
    elif name == "ArrowWeaveListDate-max":
        return "dates-max", {"dates": inputs["self"]}
    elif (
        name == "groupresult-__getitem__"
        or name == "artifacts-__getitem__"
        or name == "projectArtifactVersions-__getitem__"
        or name == "ArrowWeaveList-__getitem__"
    ):
        return "index", {"arr": inputs["self"], "index": inputs["index"]}
    return name, inputs


def convert_specific_opname_to_generic_opname(
    name: str, inputs: dict[str, typing.Any]
) -> tuple[str, dict[str, typing.Any]]:
    if name.startswith("mapped_"):
        unmapped_name = name[7:]
        return _convert_specific_opname_to_generic_opname(unmapped_name, inputs)
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


def _obj_is_node_like(data: typing.Any):
    if not isinstance(data, dict):
        return False
    return data.get("nodeType") in ["const", "output", "var", "void"]


# Non-perfect heuristic to determine if a serialized dict is likely an op
def _dict_is_op_like(data: dict):
    # Firstly, ops will only have "name" and "input" keys
    if set(data.keys()) == set(["name", "inputs"]):
        # Those keys will be str and list respectively.
        if isinstance(data["name"], str) and isinstance(data["inputs"], dict):
            # And the inputs will be dicts that are node-like
            return all(
                _obj_is_node_like(in_node) for in_node in data["inputs"].values()
            )
    return False


def convert_specific_ops_to_generic_ops_data(data):
    """Fix op call names for serialized objects containing graphs"""
    if isinstance(data, list):
        return [convert_specific_ops_to_generic_ops_data(d) for d in data]
    elif isinstance(data, dict):
        d = data
        if _dict_is_op_like(data):
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
        if _dict_is_op_like(data):
            d = copy.copy(data)
            d["name"] = graph.opuri_full_name(data["name"])
        return {k: remove_opcall_versions_data(v) for k, v in d.items()}
    return data


def fixup_node(node: graph.Node) -> graph.Node:
    node = remove_opcall_versions_node(node)
    return convert_specific_ops_to_generic_ops_node(node)


def recursively_unwrap_unions(obj):
    if isinstance(obj, list):
        return [recursively_unwrap_unions(o) for o in obj]
    if isinstance(obj, dict):
        if "_union_id" in obj and "_val" in obj:
            return recursively_unwrap_unions(obj["_val"])
        else:
            return {
                k: recursively_unwrap_unions(v)
                for k, v in obj.items()
                if k != "_union_id"
            }
    return obj


def remove_nan_and_inf(obj):
    if isinstance(obj, list):
        return [remove_nan_and_inf(o) for o in obj]
    if isinstance(obj, dict):
        return {k: remove_nan_and_inf(v) for k, v in obj.items()}
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0
    return obj


def remove_partialobject_from_types(data):
    """Convert weave-internal types like

    {"type":"PartialObject","keys":{"name":"string"},"keyless_weave_type_class":"project"}

    to types weave0 can understand. in this case:

    "project"

    """

    # TODO: check this

    if isinstance(data, list):
        return [remove_partialobject_from_types(d) for d in data]
    elif isinstance(data, dict):
        result = {}
        for key in data:
            if key == "type" and data[key] == "PartialObject":
                return data["keyless_weave_type_class"]
            result[key] = remove_partialobject_from_types(data[key])
        return result
    return data


def fixup_data(data):
    data = recursively_unwrap_unions(data)
    data = remove_opcall_versions_data(data)
    # No good! We have to do this because remoteHttp doesn't handle NaN/inf in
    # response right now.
    # TODO: fix. Encode as string and then interpret in js side.
    data = remove_nan_and_inf(data)
    data = remove_partialobject_from_types(data)
    return convert_specific_ops_to_generic_ops_data(data)
