import dataclasses
import numpy as np
import pandas as pd
import typing
from .. import weave_types as types
from ..api import op, mutation, weave_class, OpVarArgs
from .. import weave_internal
from .. import errors
from .. import execute_fast

from . import dict as dict_ops


def getitem_output_type(input_types):
    self_type = input_types["self"]
    if isinstance(self_type, types.UnionType):
        return types.UnionType(*[t.object_type for t in self_type.members])
    return self_type.object_type


@weave_class(weave_type=types.List)
class List:
    @op(input_type={"self": types.List(types.Any())}, output_type=types.Float())
    def sum(self):
        return sum(self)

    @op(
        input_type={"self": types.List(types.Any())},
        output_type=types.Int(),
    )
    def count(self):
        return len(self)

    @mutation
    def __setitem__(self, k, v):
        # TODO: copy the whole list to an actual list so we can mutate!
        #    (not good, need to implement on ArrowTableList)
        self_list = list(self)
        self_list.__setitem__(k, v)
        return self_list

    @op(
        setter=__setitem__,
        input_type={"self": types.List(types.Any()), "index": types.Int()},
        output_type=getitem_output_type,
    )
    def __getitem__(self, index):
        try:
            return self.__getitem__(index)
        except IndexError:
            return None

    @op(
        input_type={"self": types.List(types.Any()), "key": types.String()},
        # TODO: pick() is not actually part of the list interface. Its
        # only valid if the objects contained in the list are Dict/TypedDict.
        # WeaveJS makes most ops "mapped", ie they can be called on lists of the
        # object type upon which they are declared. We need to implement the same
        # behavior here, and move this out.
        output_type=lambda input_types: types.List(
            dict_ops.typeddict_pick_output_type(
                {"self": input_types["self"].object_type, "key": input_types["key"]}
            )
        ),
    )
    def pick(self, key):
        return [row.get(key) for row in self]

    @op(
        input_type={
            "self": types.List(types.Any()),
            "filter_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: input_types["self"],
    )
    def filter(self, filter_fn):
        call_results = execute_fast.fast_map_fn(self, filter_fn)
        result = []
        for row, keep in zip(self, call_results):
            if keep:
                result.append(row)
        return result

    @op(
        input_type={
            "self": types.List(types.Any()),
            "comp_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
            "column_dirs": types.Any(),
        },
        output_type=lambda input_types: input_types["self"],
    )
    def sort(self, comp_fn, column_dirs):
        call_results = execute_fast.fast_map_fn(self, comp_fn)
        # TODO: currently taking first elem of sort directions only, may not account
        # for all casees
        sort_direction = True if column_dirs[0] == "desc" else False
        return [
            r[1]
            for r in sorted(
                zip(call_results, self), key=lambda tup: tup[0], reverse=sort_direction
            )
        ]

    @op(
        input_type={
            "self": types.List(types.Any()),
            "map_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: types.List(input_types["map_fn"].output_type),
    )
    def map(self, map_fn):
        return execute_fast.fast_map_fn(self, map_fn)

    @op(
        input_type={
            "self": types.List(types.Any()),
            "group_by_fn": lambda input_types: types.Function(
                {"row": input_types["self"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: types.List(
            GroupResultType(
                input_types["self"].object_type, input_types["group_by_fn"].output_type
            )
        ),
    )
    def groupby(self, group_by_fn):
        call_results = execute_fast.fast_map_fn(self, group_by_fn)
        result = {}
        for row, group_key_items in zip(self, call_results):
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
        input_type={"arr": types.List(types.Any()), "offset": types.Number()},
        output_type=lambda input_types: input_types["arr"],
    )
    def offset(arr, offset):
        return arr[offset:]

    @op(
        input_type={"arr": types.List(types.Any()), "limit": types.Number()},
        output_type=lambda input_types: input_types["arr"],
    )
    def limit(arr, limit):
        return arr[:limit]

    @op(
        name="dropna",
        input_type={"arr": types.List(types.Any())},
        output_type=lambda input_types: input_types["arr"],
    )
    def dropna(arr):
        return [i for i in arr if i is not None]


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
        return List.pick.resolve_fn(self.list, key)

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
            "self": types.List(types.Any()),
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


@op(
    name="list-indexCheckpoint",
    input_type={"arr": types.List(types.Any())},
    output_type=lambda input_types: input_types["arr"],
)
def list_indexCheckpoint(arr):
    return arr


@op(
    name="tag-indexCheckpoint",
    input_type={"obj": types.Any()},
    output_type=types.Number(),
)
def tag_indexCheckpoint(obj):
    # TODO. Do we really need this?
    return 0


def flatten_type(list_type):
    obj_type = list_type.object_type
    if hasattr(obj_type, "object_type"):
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


def unnest_return_type(input_types):
    arr_type = input_types["arr"]
    # if isinstance(arr_type, types.UnionType):
    #     return types.union(
    #         *(unnest_return_type({"arr": m}) for m in input_types["self"].members)
    #     )
    unnested_object_property_types = {}
    for k, v_type in arr_type.object_type.property_types.items():
        if types.is_list_like(v_type):
            unnested_object_property_types[k] = v_type.object_type
        else:
            unnested_object_property_types[k] = v_type
    return types.List(types.TypedDict(unnested_object_property_types))


@op(
    name="unnest",
    input_type={"arr": types.List(types.TypedDict({}))},
    output_type=unnest_return_type,
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
        output_type=lambda input_types: input_types["obj"].key,
    )
    def key(obj):
        type_class = types.TypeRegistry.type_class_of(obj)
        return type_class.NodeMethodsClass.key.resolve_fn(obj)


class WeaveJSListInterface:
    @op(name="count")
    def count(arr: list[typing.Any]) -> int:  # type: ignore
        type_class = types.TypeRegistry.type_class_of(arr)
        return type_class.NodeMethodsClass.count.resolve_fn(arr)

    @op(name="index", output_type=index_output_type)
    def index(arr: list[typing.Any], index: int):  # type: ignore
        type_class = types.TypeRegistry.type_class_of(arr)
        return type_class.NodeMethodsClass.__getitem__.resolve_fn(arr, index)

    def pick_set(obj, k, v, action=None):
        type_class = types.TypeRegistry.type_class_of(obj)
        return type_class.NodeMethodsClass.__setitem__(obj, k, v, action=action)

    # This should not actually be part of the list interface, as its
    # only valid when contained items are lists. However, this is the
    # best place to adapt to frontend behavior, which expects a single
    # pick op that does mapping as well as TypedDict lookups.
    @op(
        name="pick",
        setter=pick_set,
        input_type={
            "obj": types.UnionType(
                types.TypedDict({}), types.List(types.TypedDict({}))
            ),
            "key": types.String(),
        },
        output_type=pick_output_type,
    )
    def pick(obj, key):  # type: ignore
        if obj == None:
            return obj
        type_class = types.TypeRegistry.type_class_of(obj)
        return type_class.NodeMethodsClass.pick.resolve_fn(obj, key)

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
    def filter(arr, filterFn):  # type: ignore
        type_class = types.TypeRegistry.type_class_of(arr)
        return type_class.NodeMethodsClass.filter.resolve_fn(arr, filterFn)

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
    def map(arr, mapFn):  # type: ignore
        type_class = types.TypeRegistry.type_class_of(arr)
        return type_class.NodeMethodsClass.map.resolve_fn(arr, mapFn)

    @op(
        name="sort",
        input_type={
            "arr": types.List(types.Any()),
            "compFn": lambda input_types: types.Function(
                {"row": input_types["arr"].object_type}, types.Any()
            ),
            "columnDirs": types.Any(),
        },
        output_type=lambda input_types: types.List(input_types["compFn"].output_type),
    )
    def sort(arr, compFn, columnDirs):  # type: ignore
        type_class = types.TypeRegistry.type_class_of(arr)
        return type_class.NodeMethodsClass.sort.resolve_fn(arr, compFn, columnDirs)

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
    def groupby(arr, groupByFn):  # type: ignore
        type_class = types.TypeRegistry.type_class_of(arr)
        try:
            return type_class.NodeMethodsClass.groupby.resolve_fn(arr, groupByFn)
        except AttributeError:
            groupby_res = List.groupby.resolve_fn(arr, groupByFn)
            return groupby_res

    @op(
        name="offset",
        input_type={"arr": types.List(types.Any()), "offset": types.Number()},
        output_type=lambda input_types: input_types["arr"],
    )
    def offset(arr, offset):
        type_class = types.TypeRegistry.type_class_of(arr)
        return type_class.NodeMethodsClass.offset.resolve_fn(arr, offset)

    @op(
        name="limit",
        input_type={"arr": types.List(types.Any()), "limit": types.Number()},
        output_type=lambda input_types: input_types["arr"],
    )
    def limit(arr, limit):
        type_class = types.TypeRegistry.type_class_of(arr)
        return type_class.NodeMethodsClass.limit.resolve_fn(arr, limit)


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


def _join_output_type(input_types):
    arr1_prop_types = input_types["arr1"].object_type.property_types
    arr2_prop_types = input_types["arr2"].object_type.property_types
    prop_types = {}
    for k in set(arr1_prop_types.keys()).union(arr2_prop_types.keys()):
        prop_types[k] = types.List(types.union(arr1_prop_types[k], arr2_prop_types[k]))
    return types.List(types.TypedDict(prop_types))


@op(
    input_type={
        "arr1": types.List(types.TypedDict({})),
        "arr2": types.List(types.TypedDict({})),
        "keyFn1": lambda input_types: types.Function(
            {"row": input_types["arr1"].object_type}, types.Any()
        ),
        "keyFn2": lambda input_types: types.Function(
            {"row": input_types["arr2"].object_type}, types.Any()
        ),
    },
    output_type=_join_output_type,
)
def join2(arr1, arr2, keyFn1, keyFn2):  # type: ignore
    arr1_keys = execute_fast.fast_map_fn(arr1, keyFn1)
    arr2_keys = execute_fast.fast_map_fn(arr2, keyFn2)
    all_keys = set(arr1_keys).union(arr2_keys)
    arr1_lookup = dict(zip(arr1_keys, arr1))
    arr2_lookup = dict(zip(arr2_keys, arr2))
    results = []
    for k in all_keys:
        arr1_row = arr1_lookup[k]
        arr2_row = arr2_lookup[k]
        row_keys = set(arr1_row.keys()).union(arr2_row.keys())
        row = {}
        for rk in row_keys:
            row[rk] = [arr1_row.get(rk), arr2_row.get(rk)]
        results.append(row)
    return results


def _join_all_output_type(input_types):
    arr_prop_types = input_types["arrs"].object_type.object_type.property_types
    prop_types = {}
    for k in arr_prop_types.keys():
        prop_types[k] = types.List(arr_prop_types[k])
    return types.List(types.TypedDict(prop_types))


@op(
    name="joinAll",
    input_type={
        "arrs": types.List(types.List(types.TypedDict({}))),
        "joinFn": lambda input_types: types.Function(
            {"row": input_types["arrs"].object_type.object_type}, types.Any()
        ),
    },
    output_type=_join_all_output_type,
)
def join_all(arrs, joinFn, outer: bool):  # type: ignore
    arr1 = arrs[0]
    arr2 = arrs[1]
    keyFn1 = joinFn
    keyFn2 = joinFn
    arr1_keys = execute_fast.fast_map_fn(arr1, keyFn1)
    arr2_keys = execute_fast.fast_map_fn(arr2, keyFn2)
    all_keys = set(arr1_keys).union(arr2_keys)
    arr1_lookup = dict(zip(arr1_keys, arr1))
    arr2_lookup = dict(zip(arr2_keys, arr2))
    results = []
    for k in all_keys:
        arr1_row = arr1_lookup[k]
        arr2_row = arr2_lookup[k]
        row_keys = set(arr1_row.keys()).union(arr2_row.keys())
        row = {}
        for rk in row_keys:
            row[rk] = [arr1_row.get(rk), arr2_row.get(rk)]
        results.append(row)
    return results
