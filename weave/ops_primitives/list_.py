import dataclasses
import numpy as np
import pandas as pd
import typing
from .. import box
from .. import weave_types as types
from ..api import Node, op, mutation, weave_class, OpVarArgs
from .. import weave_internal
from .. import errors
from .. import execute_fast
from ..language_features.tagging import make_tag_getter_op, tag_store, tagged_value_type

from . import dict as dict_ops


def general_picker(obj, key):
    return [row.get(key) for row in obj]


@weave_class(weave_type=types.List)
class List:
    @op(name="count", input_type={"arr": types.List(types.Any())})
    def count(arr: list[typing.Any]) -> int:  # type: ignore
        return len(arr)

    @mutation
    def __setitem__(self, k, v):
        # TODO: copy the whole list to an actual list so we can mutate!
        #    (not good, need to implement on ArrowTableList)
        self_list = list(self)
        self_list.__setitem__(k, v)
        return self_list

    @op(
        name="index",
        setter=__setitem__,
        input_type={"arr": types.List(types.Any()), "index": types.Int()},
        output_type=lambda input_types: input_types["arr"].object_type,
    )
    def __getitem__(arr, index):
        try:
            return arr.__getitem__(index)
        except IndexError:
            return None

    @op(
        name="filter",
        input_type={
            "arr": types.List(types.Any()),
            "filterFn": lambda input_types: types.Function(
                {"row": input_types["arr"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: input_types["arr"],
    )
    def filter(arr, filterFn):
        call_results = execute_fast.fast_map_fn(arr, filterFn)
        result = []
        for row, keep in zip(arr, call_results):
            if keep:
                result.append(row)
        return result

    @op(
        name="sort",
        input_type={
            "arr": types.List(types.Any()),
            "compFn": lambda input_types: types.Function(
                {"row": input_types["arr"].object_type}, types.Any()
            ),
            "columnDirs": types.Any(),
        },
        output_type=lambda input_types: input_types["arr"],
    )
    def sort(arr, compFn, columnDirs):
        call_results = execute_fast.fast_map_fn(arr, compFn)
        # TODO: currently taking first elem of sort directions only, may not account
        # for all casees
        sort_direction = True if columnDirs[0] == "desc" else False
        return [
            r[1]
            for r in sorted(
                zip(call_results, arr), key=lambda tup: tup[0], reverse=sort_direction
            )
        ]

    @op(
        name="map",
        input_type={
            "arr": types.List(types.Any()),
            "mapFn": lambda input_types: types.Function(
                {"row": input_types["arr"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: types.List(input_types["mapFn"].output_type),
    )
    def map(arr, mapFn):
        return execute_fast.fast_map_fn(arr, mapFn)

    @op(
        name="groupby",
        input_type={
            "arr": types.List(types.Any()),
            "groupByFn": lambda input_types: types.Function(
                {"row": input_types["arr"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: types.List(
            GroupResultType(
                input_types["arr"].object_type, input_types["groupByFn"].output_type
            )
        ),
    )
    def groupby(arr, groupByFn):
        call_results = execute_fast.fast_map_fn(arr, groupByFn)
        result = {}
        for row, group_key_items in zip(arr, call_results):
            import json

            group_key_s = json.dumps(group_key_items)
            if group_key_s not in result:
                result[group_key_s] = (group_key_items, [])
            result[group_key_s][1].append(row)
        # TODO: relying on dict ordering???
        grs = []
        for group_result in result.values():
            grs.append(GroupResult(group_result[1], group_result[0]))
        return grs

    @op(
        name="offset",
        input_type={"arr": types.List(types.Any()), "offset": types.Number()},
        output_type=lambda input_types: input_types["arr"],
    )
    def offset(arr, offset):
        return arr[offset:]

    @op(
        name="limit",
        input_type={"arr": types.List(types.Any()), "limit": types.Number()},
        output_type=lambda input_types: input_types["arr"],
    )
    def limit(arr, limit):
        return arr[:limit]

    @op(
        name="dropna",
        input_type={"arr": types.List(types.Any())},
        # HACK: This is a case of actually wanting to perform an op on a TYPE!
        output_type=lambda input_types: handle_dropna_output_type(input_types),
    )
    def dropna(arr):
        return [i for i in arr if i is not None]

    @op(
        name="concat",
        input_type={"arr": types.List(types.List(types.Any()))},
        output_type=lambda input_types: input_types["arr"].object_type,
    )
    def concat(arr):
        res = []
        for sublist in arr:
            if not tag_store.is_tagged(sublist):
                res.extend(sublist)
            else:
                tags = tag_store.get_tags(sublist)
                for i in sublist:
                    obj = box.box(i)
                    tag_store.add_tags(obj, tags)
                    res.append(obj)
        return res


def handle_dropna_output_type(input_types):
    # import pdb; pdb.set_trace()
    return (
        types.List.make({"object_type": input_types["arr"].object_type.non_none()})
        if isinstance(input_types["arr"].object_type, Node)
        else types.List(types.non_none(input_types["arr"].object_type))
    )


@dataclasses.dataclass(frozen=True)
class GroupResultType(types.ObjectType):
    name = "groupresult"

    object_type: types.Type = types.Any()
    key: types.Type = types.Any()

    @classmethod
    def type_of_instance(cls, obj):
        return cls(
            types.TypeRegistry.type_of(obj.list).object_type,
            types.TypeRegistry.type_of(obj.key),
        )

    def property_types(self):
        return {"list": types.List(self.object_type), "key": self.key}


def group_result_index_output_type(input_types):
    # THIS IS NO GOOD
    # TODO: need to fix Const type so we don't need this.
    self_type = input_types["self"]
    if isinstance(self_type, types.Const):
        return self_type.val_type.object_type
    else:
        return self_type.object_type


@weave_class(weave_type=GroupResultType)
class GroupResult:
    def __init__(self, list, key):
        self.list = list
        self.key = key

    @property
    def var_item(self):
        return weave_internal.make_var_node(self.type.object_type, "row")

    @op(output_type=lambda input_types: input_types["self"].key)
    def key(self):
        return self.key

    @op(output_type=types.Any())
    def pick(self, key: str):
        return general_picker(self.list, key)

    @op()
    def count(self) -> int:
        return len(self.list)

    @op(output_type=group_result_index_output_type)
    def __getitem__(self, index: int):
        return List.__getitem__.resolve_fn(self.list, index)

    @op(
        input_type={
            "self": GroupResultType(),
            "map_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: types.List(input_types["map_fn"].output_type),
    )
    def map(self, map_fn):
        return List.map.resolve_fn(self.list, map_fn)

    @op(
        input_type={
            "group_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: types.List(
            GroupResultType(input_types["self"].object_type)
        ),
    )
    def groupby(self, group_fn):
        return List.groupby.resolve_fn(self.list, group_fn)


GroupResultType.instance_class = GroupResult
GroupResultType.instance_classes = GroupResult


### TODO Move these ops onto List class and make part of the List interface


@mutation
def index_checkpoint_setter(arr, new_arr):
    return new_arr


@op(
    name="list-createIndexCheckpointTag",
    setter=index_checkpoint_setter,
    input_type={"arr": types.List(types.Any())},
    output_type=lambda input_types: types.List(
        tagged_value_type.TaggedValueType(
            types.TypedDict({"index": types.Number()}), input_types["arr"].object_type
        )
    ),
)
def list_indexCheckpoint(arr):
    # TODO: I think this will be inefficient for larger lists
    # or other data structures. Need to improve this.
    # if not isinstance(arr, list):
    #     return arr
    res = []
    for item in arr:
        item = box.box(item)
        tag_store.add_tags(item, {"index": len(res)})
        res.append(item)
    return res


index_checkpoint_tag_getter_op = make_tag_getter_op.make_tag_getter_op(
    "index", types.Number(), op_name="tag-indexCheckpoint"
)


def is_list_like(list_type_or_node):
    if isinstance(list_type_or_node, Node):
        return is_list_like(list_type_or_node.type)
    return hasattr(list_type_or_node, "object_type")


def flatten_type(list_type):
    obj_type = list_type.object_type
    if is_list_like(obj_type):
        return flatten_type(obj_type)
    return types.List(obj_type)


def flatten_return_type(input_types):
    return flatten_type(input_types["arr"])


def _flatten(l):
    if isinstance(l, list):
        return sum((_flatten(o) for o in l), [])
    elif isinstance(l, GroupResult):
        return sum((_flatten(o) for o in l.list), [])
    else:
        return [l]


@op(
    name="flatten",
    input_type={"arr": types.List(types.Any())},
    output_type=flatten_return_type,
)
def flatten(arr):
    return _flatten(list(arr))


@op(
    name="unnest",
    input_type={"arr": types.List(types.TypedDict({}))},
    output_type=lambda input_types: input_types["arr"],
)
def unnest(arr):
    if not arr:
        return arr
    list_cols = []
    # Very expensive to recompute type here. We already have it!
    # TODO: need a way to get argument types inside of resolver bodies.
    arr_type = types.TypeRegistry.type_of(arr)
    for k, v_type in arr_type.object_type.property_types.items():
        if types.is_list_like(v_type):
            list_cols.append(k)
    if not list_cols:
        return arr
    return pd.DataFrame(arr).explode(list_cols).to_dict("records")


@op(
    name="unique",
    input_type={"arr": types.List(types.Any())},
    output_type=lambda input_types: input_types["arr"],
)
def unique(arr):
    if not arr:
        return arr
    res = np.unique(arr)
    return res.tolist()


def index_output_type(input_types):
    # THIS IS NO GOOD
    # TODO: need to fix Const type so we don't need this.
    self_type = input_types["arr"]
    if isinstance(self_type, types.Const):
        return self_type.val_type.object_type
    else:
        return self_type.object_type


def pick_output_type(input_types):
    # This is heinous. It handles mapped pick as well as regular pick.
    # Doesn't support all the fancy stuff with '*' that the frontend does yet.
    # TODO: fix, probably by a better mapped op implementation, and possible some
    # clearner way of implementing nice type logic.
    if not isinstance(input_types["key"], types.Const):
        return types.UnknownType()
    key = input_types["key"].val
    self_type = input_types["obj"]
    object_type = self_type
    is_list = False
    # Ew, this is the best way to determine if a Type looks like a list
    # (like pandas, sql list types).
    # TODO: fix
    if hasattr(self_type, "object_type"):
        object_type = self_type.object_type
        is_list = True
    if isinstance(object_type, types.Dict):
        output_type = object_type.object_type
    elif isinstance(object_type, types.TypedDict):
        property_types = object_type.property_types
        output_type = property_types.get(key)
        if output_type is None:
            output_type = types.none_type
    else:
        raise errors.WeaveInternalError(
            "pick received invalid input types: %s" % input_types
        )
    if is_list:
        output_type = types.List(output_type)
    return output_type


class WeaveGroupResultInterface:
    @op(
        name="group-groupkey",
        input_type={"obj": GroupResultType()},
        output_type=lambda input_types: input_types["obj"]._key,
    )
    def key(obj):
        type_class = types.TypeRegistry.type_class_of(obj)
        return type_class.NodeMethodsClass.key.resolve_fn(obj)


class WeaveJSListInterface:
    def count(arr):
        arr_node = weave_internal._ensure_node("count", arr, None, None)
        return weave_internal.make_output_node(
            types.Number(),
            "count",
            {
                "arr": arr_node,
            },
        )

    def index(arr, index):
        arr_node = weave_internal._ensure_node("index", arr, None, None)
        return weave_internal.make_output_node(
            arr_node.type.object_type,
            "index",
            {
                "arr": arr_node,
                "index": weave_internal._ensure_node("index", index, None, None),
            },
        )

    def filter(arr, filterFn):
        arr_node = weave_internal._ensure_node("filter", arr, None, None)
        return weave_internal.make_output_node(
            arr_node.type,
            "filter",
            {
                "arr": arr_node,
                "filterFn": weave_internal._ensure_node(
                    "filter",
                    filterFn,
                    types.Function({"row": arr_node.type.object_type}, types.Any()),
                    None,
                ),
            },
        )

    def map(arr, mapFn):
        arr_node = weave_internal._ensure_node("map", arr, None, None)
        return weave_internal.make_output_node(
            arr_node.type,
            "map",
            {
                "arr": arr_node,
                "mapFn": weave_internal._ensure_node(
                    "map",
                    mapFn,
                    types.Function({"row": arr_node.type.object_type}, types.Any()),
                    None,
                ),
            },
        )

    def sort(arr, compFn, columnDirs):
        arr_node = weave_internal._ensure_node("sort", arr, None, None)
        return weave_internal.make_output_node(
            arr_node.type,
            "sort",
            {
                "arr": arr_node,
                "compFn": weave_internal._ensure_node(
                    "sort",
                    compFn,
                    types.Function({"row": arr_node.type.object_type}, types.Any()),
                    None,
                ),
                "columnDirs": types.Any(),
            },
        )

    def groupby(arr, groupByFn):
        arr_node = weave_internal._ensure_node("groupby", arr, None, None)
        return weave_internal.make_output_node(
            types.List(GroupResultType(arr_node.type.object_type)),
            "groupby",
            {
                "arr": arr_node,
                "groupByFn": weave_internal._ensure_node(
                    "groupby",
                    groupByFn,
                    types.Function({"row": arr_node.type.object_type}, types.Any()),
                    None,
                ),
            },
        )

    def offset(arr, offset):
        arr_node = weave_internal._ensure_node("offset", arr, None, None)
        return weave_internal.make_output_node(
            arr_node.type,
            "offset",
            {
                "arr": arr_node,
                "offset": weave_internal._ensure_node(
                    "offset",
                    offset,
                    None,
                    None,
                ),
            },
        )

    def limit(arr, limit):
        arr_node = weave_internal._ensure_node("limit", arr, None, None)
        return weave_internal.make_output_node(
            arr_node.type,
            "limit",
            {
                "arr": arr_node,
                "limit": weave_internal._ensure_node(
                    "limit",
                    limit,
                    None,
                    None,
                ),
            },
        )


def list_return_type(input_types):
    its = []
    for input_type in input_types.values():
        if isinstance(input_type, types.Const):
            input_type = input_type.val_type
        its.append(input_type)
    ret = types.List(types.union(*its))
    return ret


@op(
    name="list",
    input_type=OpVarArgs(types.Any()),
    output_type=list_return_type,
)
def make_list(**l):
    return list(l.values())
