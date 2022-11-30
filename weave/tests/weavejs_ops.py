# WeaveJS ops used for testing. These are not used in production.

from ..ops_primitives._dict_utils import typeddict_pick_output_type
from .. import weave_types as types
from .. import graph
from .. import weave_internal
from ..language_features.tagging import tagged_value_type


def ensure_node(v):
    if isinstance(v, graph.Node):
        return v
    return weave_internal.const(v)


def weavejs_pick(obj: graph.Node, key: str):
    return weave_internal.make_output_node(
        typeddict_pick_output_type(
            {"self": obj.type, "key": types.Const(types.String(), key)}
        ),
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
    return weave_internal.make_output_node(
        arr_node.type.object_type,
        "index",
        {
            "arr": arr_node,
            "index": ensure_node(index),
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
            "columnDirs": types.Any(),
        },
    )


def groupby(arr, groupByFn):
    arr_node = ensure_node(arr)
    groupByFn_node = ensure_node(groupByFn)
    return weave_internal.make_output_node(
        types.List(
            tagged_value_type.TaggedValueType(
                types.TypedDict({"groupKey": groupByFn_node.type.output_type}),
                arr_node.type,
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
    return weave_internal.make_output_node(
        file_node.type,
        "file-type",
        {
            "file": file_node,
        },
    )
