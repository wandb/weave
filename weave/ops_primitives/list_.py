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
from .. import op_def
from ..language_features.tagging import make_tag_getter_op, tag_store, tagged_value_type
import functools


def _map_each_function_type(input_types: dict[str, types.Type]) -> types.Function:
    if types.List().assign_type(input_types["arr"]):
        return _map_each_function_type(
            {"arr": typing.cast(types.List, input_types["arr"]).object_type}
        )
    return types.Function({"row": input_types["arr"]}, types.Any())


def _list_ndims(list_type: types.Type) -> int:
    if types.List().assign_type(list_type):
        return 1 + _list_ndims(typing.cast(types.List, list_type).object_type)
    return 0


def _map_each_output_type(input_types: dict[str, types.Type]):
    map_each_function_type = input_types["mapFn"]
    list_ndims = _list_ndims(input_types["arr"])
    output_type = typing.cast(types.Function, map_each_function_type).output_type
    for _ in range(list_ndims):
        output_type = types.List(output_type)
    return output_type


def _map_each(arr: list, fn):
    if isinstance(arr, list) and len(arr) > 0 and isinstance(arr[0], list):
        return [_map_each(item, fn) for item in arr]
    return execute_fast.fast_map_fn(arr, fn)


def getitem_output_type(input_types):
    self_type = input_types["arr"]
    if isinstance(self_type, types.UnionType):
        return types.UnionType(*[t.object_type for t in self_type.members])
    return self_type.object_type


def general_picker(obj, key):
    return [row.get(key) for row in obj]


@weave_class(weave_type=types.List)
class List:
    @op(name="count", input_type={"arr": types.List(types.Any())})
    def count(arr: list[typing.Any]) -> int:  # type: ignore
        return len(arr)

    def __setitem__(self, k, v, action=None):
        # TODO: copy the whole list to an actual list so we can mutate!
        #    (not good, need to implement on ArrowTableList)
        self_list = list(self)
        self_list.__setitem__(k, v)
        return self_list

    @op(
        setter=__setitem__,
        input_type={"arr": types.List(types.Any()), "index": types.Int()},
        output_type=getitem_output_type,
    )
    def __getitem__(arr, index):
        # This is a hack to resolve the fact that WeaveJS expects groupby to
        # return TaggedValue, while Weave Python currently still returns GroupResult
        # TODO: Remove when we switch Weave Python over to using TaggedValue for this
        # case.
        if isinstance(arr.__getitem__, op_def.OpDef):
            return arr.__getitem__.raw_resolve_fn(arr, index)
        try:
            return arr.__getitem__(index)
        except IndexError:
            return None

    @op(
        name="filter",
        input_type={
            "arr": types.List(types.Any()),
            "filterFn": lambda input_types: types.Function(
                {"row": input_types["arr"].object_type}, types.optional(types.Boolean())
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
                {"row": input_types["arr"].object_type}, types.List(types.Any())
            ),
            "columnDirs": types.List(types.String()),
        },
        output_type=lambda input_types: input_types["arr"],
    )
    def sort(arr, compFn, columnDirs):
        def cmp(a, b):
            a_comp_res = a[0]
            b_comp_res = b[0]
            for a_res, b_res, c_dir in zip(a_comp_res, b_comp_res, columnDirs):
                dir_adjust = -1 if c_dir == "desc" else 1
                if a_res < b_res:
                    return -1 * dir_adjust
                elif a_res > b_res:
                    return 1 * dir_adjust
            return 0

        call_results = execute_fast.fast_map_fn(arr, compFn)
        sortable_results = zip(call_results, arr)
        sorted_results = sorted(sortable_results, key=functools.cmp_to_key(cmp))
        return [res[1] for res in sorted_results]

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
        name="mapEach",
        input_type={
            "arr": types.List(types.Any()),
            "mapFn": _map_each_function_type,
        },
        output_type=_map_each_output_type,
    )
    def map_each(arr, mapFn):
        return _map_each(arr, mapFn)

    @op(
        name="groupby",
        input_type={
            "arr": types.List(types.Any()),
            "groupByFn": lambda input_types: types.Function(
                {"row": input_types["arr"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: types.List(
            tagged_value_type.TaggedValueType(
                types.TypedDict(
                    {
                        "groupKey": input_types["groupByFn"].output_type,
                    }
                ),
                input_types["arr"],
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
        grs = []
        for group_result in result.values():
            item = box.box(group_result[1])
            tag_store.add_tags(item, {"groupKey": group_result[0]})
            grs.append(item)
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
        output_type=lambda input_types: input_types["arr"],
    )
    def dropna(arr):
        return [i for i in arr if i is not None]

    @op(
        name="concat",
        input_type={
            "arr": types.List(types.union(types.NoneType(), types.List(types.Any())))
        },
        output_type=lambda input_types: input_types["arr"].object_type,
    )
    def concat(arr):
        res = []
        arr = [item for item in arr if item != None]
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


@dataclasses.dataclass(frozen=True)
class GroupResultType(types.ObjectType):
    _base_type = types.List()
    name = "groupresult"

    list: types.Type = types.List(types.Any())
    key: types.Type = types.Any()

    @property
    def object_type(self):
        return self.list.object_type

    @classmethod
    def type_of_instance(cls, obj):
        return cls(
            types.TypeRegistry.type_of(obj.list),
            types.TypeRegistry.type_of(obj.key),
        )

    def property_types(self):
        return {"list": self.list, "key": self.key}


def group_result_index_output_type(input_types):
    # THIS IS NO GOOD
    # TODO: need to fix Const type so we don't need this.
    self_type = input_types["self"]
    if isinstance(self_type, types.Const):
        return self_type.val_type.list.object_type
    else:
        return self_type.list.object_type


@weave_class(weave_type=GroupResultType)
class GroupResult:
    def __init__(self, list, key):
        self.list = list
        self.key = key

    @property
    def var_item(self):
        return weave_internal.make_var_node(self.type.object_type, "row")

    def __iter__(self):
        return iter(self.list)

    def __len__(self):
        return len(self.list)

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
            GroupResultType(input_types["self"])
        ),
    )
    def groupby(self, group_fn):
        return List.groupby.resolve_fn(self.list, group_fn)


GroupResultType.instance_class = GroupResult
GroupResultType.instance_classes = GroupResult


### TODO Move these ops onto List class and make part of the List interface


def index_checkpoint_setter(arr, new_arr):
    return new_arr


@op(
    name="list-createIndexCheckpointTag",
    setter=index_checkpoint_setter,
    input_type={"arr": types.List(types.Any())},
    output_type=lambda input_types: types.List(
        tagged_value_type.TaggedValueType(
            types.TypedDict({"indexCheckpoint": types.Number()}),
            input_types["arr"].object_type,
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
        tag_store.add_tags(item, {"indexCheckpoint": len(res)})
        res.append(item)
    return res


index_checkpoint_tag_getter_op = make_tag_getter_op.make_tag_getter_op(
    "indexCheckpoint", types.Int(), op_name="tag-indexCheckpoint"
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


def unnest_return_type(input_types):
    arr_type = input_types["arr"]
    # if isinstance(arr_type, types.UnionType):
    #     return types.union(
    #         *(unnest_return_type({"arr": m}) for m in input_types["self"].members)
    #     )
    unnested_object_property_types = {}
    for k, v_type in arr_type.object_type.property_types.items():
        if types.List().assign_type(v_type):
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
        if types.List().assign_type(v_type):
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


group_tag_getter_op = make_tag_getter_op.make_tag_getter_op(
    "groupKey", types.Any(), op_name="group-groupkey"
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


@op(name="range")
def op_range(start: int, stop: int, step: int) -> list[int]:
    return list(range(start, stop, step))
