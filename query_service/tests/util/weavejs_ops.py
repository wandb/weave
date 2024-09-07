# WeaveJS ops used for testing. These are not used in production.

from weave.legacy.weave import graph, weave_internal
from weave.legacy.weave import weave_types as types
from weave.legacy.weave._dict_utils import typeddict_pick_output_type
from weave.legacy.weave.language_features.tagging import tagged_value_type
from weave.legacy.weave.language_features.tagging.tagging_op_logic import (
    op_get_tag_type_resolver,
    op_make_type_tagged_resolver,
)


def ensure_node(v):
    if isinstance(v, graph.Node):
        return v
    return weave_internal.const(v)


def weavejs_pick(obj: graph.Node, key: str):
    raw_output_type = typeddict_pick_output_type(
        {"self": obj.type, "key": types.Const(types.String(), key)}
    )
    output_type = op_make_type_tagged_resolver(
        raw_output_type, op_get_tag_type_resolver(obj.type)
    )
    return weave_internal.make_output_node(
        output_type,
        "pick",
        {"obj": obj, "key": graph.ConstNode(types.String(), key)},
    )


def count(arr):
    arr_node = ensure_node(arr)
    return weave_internal.make_output_node(
        types.Number(),
        "count",
        {
            "arr": arr_node,
        },
    )


def index(arr, index):
    arr_node = ensure_node(arr)
    index_node = ensure_node(index)
    output_type = op_make_type_tagged_resolver(
        arr_node.type.object_type, op_get_tag_type_resolver(arr_node.type)
    )
    return weave_internal.make_output_node(
        output_type,
        "index",
        {
            "arr": arr_node,
            "index": index_node,
        },
    )


def filter(arr, filterFn):
    arr_node = ensure_node(arr)
    return weave_internal.make_output_node(
        arr_node.type,
        "filter",
        {
            "arr": arr_node,
            "filterFn": ensure_node(filterFn),
        },
    )


def map(arr, mapFn):
    arr_node = ensure_node(arr)
    return weave_internal.make_output_node(
        arr_node.type,
        "map",
        {
            "arr": arr_node,
            "mapFn": ensure_node(mapFn),
        },
    )


def sort(arr, compFn, columnDirs):
    arr_node = ensure_node(arr)
    return weave_internal.make_output_node(
        arr_node.type,
        "sort",
        {
            "arr": arr_node,
            "compFn": ensure_node(compFn),
            "columnDirs": ensure_node(columnDirs),
        },
    )


def groupby(arr, groupByFn):
    arr_node = ensure_node(arr)
    groupByFn_node = ensure_node(groupByFn)
    return weave_internal.make_output_node(
        types.List(
            tagged_value_type.TaggedValueType(
                types.TypedDict({"groupKey": groupByFn_node.type.output_type}),
                types.List(arr_node.type.object_type),
            )
        ),
        "groupby",
        {"arr": arr_node, "groupByFn": groupByFn_node},
    )


def offset(arr, offset):
    arr_node = ensure_node(arr)
    return weave_internal.make_output_node(
        arr_node.type,
        "offset",
        {
            "arr": arr_node,
            "offset": ensure_node(offset),
        },
    )


def limit(arr, limit):
    arr_node = ensure_node(arr)
    return weave_internal.make_output_node(
        arr_node.type,
        "limit",
        {
            "arr": arr_node,
            "limit": ensure_node(limit),
        },
    )


def file_type(file):
    file_node = ensure_node(file)
    output_type = op_make_type_tagged_resolver(
        types.TypeType(), op_get_tag_type_resolver(file_node.type)
    )
    return weave_internal.make_output_node(
        output_type,
        "file-type",
        {
            "file": file_node,
        },
    )
