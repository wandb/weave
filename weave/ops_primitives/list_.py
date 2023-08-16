import numpy as np
import pandas as pd
import json
import itertools
import typing

from . import projection_utils

from ._dict_utils import tag_aware_dict_val_for_escaped_key
from .. import box
from .. import weave_types as types
from ..api import Node, op, weave_class, OpVarArgs
from .. import errors
from .. import execute_fast
from .. import storage
from ..language_features.tagging import (
    tag_store,
    tagged_value_type,
    tagged_value_type_helpers,
)


import functools


def getitem_output_type(input_types, list_type=types.List):
    input_type_values = list(input_types.values())
    self_type = input_type_values[0]
    index_type = input_type_values[1]
    if self_type.object_type == types.UnknownType():
        # This happens when we're indexing an empty list
        obj_res = types.NoneType()
    else:
        obj_res = self_type.object_type
    if is_list_like(index_type):
        return list_type(obj_res)
    return obj_res


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
        input_type={
            "arr": types.List(types.Any()),
        },
        output_type=getitem_output_type,
    )
    def __getitem__(
        arr,
        index: typing.Optional[typing.Union[int, typing.List[typing.Optional[int]]]],
    ):
        if index == None:
            return None
        if isinstance(index, int):
            try:
                return arr.__getitem__(index)
            except IndexError:
                return None
        # otherwise we have a list-like (list or AWL)
        indexes = typing.cast(typing.List[typing.Optional[int]], index)
        result: list = []
        for i in indexes:
            if i == None:
                result.append(None)
            else:
                try:
                    result.append(arr.__getitem__(i))
                except IndexError:
                    result.append(None)
        return result

    @op(
        name="filter",
        input_type={
            "arr": types.List(types.Any()),
            "filterFn": lambda input_types: types.Function(
                {"row": input_types["arr"].object_type, "index": types.Int()},
                types.optional(types.Boolean()),
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
                if a_res == None and b_res == None:
                    continue
                elif a_res == None:
                    return -1 * dir_adjust
                elif b_res == None:
                    return 1 * dir_adjust

                try:
                    lt = a_res < b_res
                except TypeError:
                    a_res = str(a_res)
                    b_res = str(b_res)
                    lt = a_res < b_res

                if lt:
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
                {"row": input_types["arr"].object_type, "index": types.Int()},
                types.Any(),
            ),
        },
        output_type=lambda input_types: types.List(input_types["mapFn"].output_type),
    )
    def map(arr, mapFn):
        return execute_fast.fast_map_fn(arr, mapFn)

    # TODO: This should be hidden!
    @op(
        name="_listmap",
        input_type={
            "arr": types.List(types.Any()),
            "mapFn": lambda input_types: types.Function(
                {"row": input_types["arr"].object_type}, types.Any()
            ),
        },
        output_type=lambda input_types: types.List(input_types["mapFn"].output_type),
    )
    def _listmap(arr, mapFn):
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
        # Start a new tagging context since we don't want the tags messing
        # with the groupby keys
        with tag_store.new_tagging_context():
            for row, group_key_items in zip(arr, call_results):
                group_key_s = json.dumps(storage.to_python(group_key_items))
                # logging.error("groupby group_key_s: %s", group_key_s)
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
        output_type=lambda input_types: types.List(
            types.non_none(input_types["arr"].object_type)
            if types.non_none(input_types["arr"].object_type) != types.Invalid()
            else types.NoneType()
        ),
    )
    def dropna(arr):
        return [i for i in arr if i != None]

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


def group_result_index_output_type(input_types):
    # THIS IS NO GOOD
    # TODO: need to fix Const type so we don't need this.
    self_type = input_types["self"]
    if isinstance(self_type, types.Const):
        return self_type.val_type.list.object_type
    else:
        return self_type.list.object_type


### TODO Move these ops onto List class and make part of the List interface


def _map_each_function_type(input_types: dict[str, types.Type]) -> types.Function:
    if types.List().assign_type(input_types["arr"]):
        return _map_each_function_type(
            {"arr": typing.cast(types.List, input_types["arr"]).object_type}
        )
    return types.Function({"row": input_types["arr"]}, types.Any())


def _map_each_output_type(input_types: dict[str, types.Type]):
    # propagate tags in output type
    map_each_function_type = input_types["mapFn"]
    output_type = typing.cast(types.Function, map_each_function_type).output_type

    def get_next_type(t: types.Type) -> types.Type:
        if types.List().assign_type(t):
            t_as_list = typing.cast(types.List, t)
            if tagged_value_type_helpers.is_tagged_value_type(t):
                t_as_tagged = typing.cast(tagged_value_type.TaggedValueType, t)
                return tagged_value_type.TaggedValueType(
                    t_as_tagged.tag,
                    types.List(
                        get_next_type(
                            typing.cast(types.List, t_as_tagged.value).object_type
                        )
                    ),
                )
            return types.List(get_next_type(t_as_list.object_type))
        elif tagged_value_type_helpers.is_tagged_value_type(t):
            t_as_tagged = typing.cast(tagged_value_type.TaggedValueType, t)
            return tagged_value_type.TaggedValueType(t_as_tagged.tag, output_type)
        return output_type

    return get_next_type(input_types["arr"])


def _map_each(arr: list, fn):
    existing_tags = [
        tag_store.get_tags(item) if tag_store.is_tagged(item) else None for item in arr
    ]

    if isinstance(arr, list) and len(arr) > 0 and isinstance(arr[0], list):
        result = [_map_each(item, fn) for item in arr]
    else:
        result = execute_fast.fast_map_fn(arr, fn)

    for i, item in enumerate(result):
        maybe_existing_tags = existing_tags[i]
        if maybe_existing_tags is not None:
            result[i] = tag_store.add_tags(box.box(item), maybe_existing_tags)

    return result


@op(
    name="mapEach",
    input_type={
        "arr": types.Any(),
        "mapFn": _map_each_function_type,
    },
    output_type=_map_each_output_type,
)
def map_each(arr, mapFn):
    arr_is_list = isinstance(arr, list)
    if not arr_is_list:
        arr = [arr]
    res = _map_each(arr, mapFn)
    if not arr_is_list:
        res = res[0]
    return res


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


def is_list_like(list_type_or_node):
    if isinstance(list_type_or_node, Node):
        return types.is_list_like(list_type_or_node.type)
    return types.is_list_like(list_type_or_node)


def flatten_type(list_type):
    obj_type = list_type.object_type
    if is_list_like(obj_type):
        return flatten_type(obj_type)
    return types.List(obj_type)


def flatten_return_type(input_types):
    return flatten_type(input_types["arr"])


def _flatten(l):
    from ..ops_arrow import ArrowWeaveList
    from ..ops_arrow.arrow_tags import pushdown_list_tags

    if isinstance(l, list):
        tags = None
        if tag_store.is_tagged(l):
            tags = tag_store.get_tags(l)

        def tag_wrapper(item):
            if tags is not None:
                return tag_store.add_tags(box.box(item), tags)
            return item

        return sum((_flatten(tag_wrapper(o)) for o in l), [])
    elif isinstance(l, ArrowWeaveList):
        return pushdown_list_tags(l).to_pylist_tagged()
    else:
        return [l]


@op(
    name="flatten",
    input_type={"arr": types.List(types.Any())},
    output_type=flatten_return_type,
)
def flatten(arr):
    return _flatten(arr)


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
    return list(dict.fromkeys(arr))


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


def list_return_type(input_types):
    return types.List(types.union(*input_types.values()))


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


def _join_2_output_row_type(input_types):
    both_aliases_are_consts = isinstance(
        input_types["alias1"], types.Const
    ) and isinstance(input_types["alias2"], types.Const)
    arr1_obj_type = input_types["arr1"].object_type
    arr2_obj_type = input_types["arr2"].object_type
    if both_aliases_are_consts:
        alias_1 = input_types["alias1"].val
        alias_2 = input_types["alias2"].val
        result_row_type = types.TypedDict(
            {
                # Technically this optionality should depend on the `outers` flags
                # but making the implementation more loose for now to match Weave1
                alias_1: types.optional(arr1_obj_type),
                alias_2: types.optional(arr2_obj_type),
            }
        )
    else:
        result_row_type = types.Dict(
            types.String(),
            types.union(types.optional(arr1_obj_type), types.optional(arr2_obj_type)),
        )

    join_obj_type = types.optional(
        types.union(
            input_types["join1Fn"].output_type,
            input_types["join2Fn"].output_type,
        )
    )
    row_tag_type = types.TypedDict({"joinObj": join_obj_type})

    return tagged_value_type.TaggedValueType(row_tag_type, result_row_type)


def _join_2_output_type(input_types):
    return types.List(_join_2_output_row_type(input_types))


@op(
    name="join",
    input_type={
        "arr1": types.List(),
        "arr2": types.List(),
        "join1Fn": lambda input_types: types.Function(
            {"row": input_types["arr1"].object_type}, types.Any()
        ),
        "join2Fn": lambda input_types: types.Function(
            {"row": input_types["arr2"].object_type}, types.Any()
        ),
        "alias1": types.String(),
        "alias2": types.String(),
        "leftOuter": types.Boolean(),
        "rightOuter": types.Boolean(),
    },
    output_type=_join_2_output_type,
)
def join_2(arr1, arr2, join1Fn, join2Fn, alias1, alias2, leftOuter, rightOuter):
    table1_join_keys = execute_fast.fast_map_fn(arr1, join1Fn)
    table2_join_keys = execute_fast.fast_map_fn(arr2, join2Fn)

    jk_to_idx: dict[str, typing.Tuple[list[int], list[int], typing.Any]] = {}
    for i, jk in enumerate(table1_join_keys):
        if jk != None:
            safe_jk = json.dumps(box.unbox(jk))
            jk_to_idx.setdefault(safe_jk, ([], [], jk))[0].append(i)
    for i, jk in enumerate(table2_join_keys):
        if jk != None:
            safe_jk = json.dumps(box.unbox(jk))
            jk_to_idx.setdefault(safe_jk, ([], [], jk))[1].append(i)

    rows = []
    for idx1, idx2, jk in jk_to_idx.values():
        tag = {"joinObj": jk}
        if len(idx1) == 0 and rightOuter:
            idx1 = [None]
        if len(idx2) == 0 and leftOuter:
            idx2 = [None]
        for i1 in idx1:
            for i2 in idx2:
                row = {}
                if i1 != None:
                    row[alias1] = arr1[i1]
                else:
                    row[alias1] = None
                if i2 != None:
                    row[alias2] = arr2[i2]
                else:
                    row[alias2] = None
                rows.append(tag_store.add_tags(box.box(row), tag))
    return rows


def _join_all_output_type(input_types):
    arr_prop_types = input_types["arrs"].object_type.object_type.property_types
    prop_types = {}
    for k in arr_prop_types.keys():
        prop_types[k] = types.List(arr_prop_types[k])
    inner_type = types.TypedDict(prop_types)
    tag_type = types.TypedDict({"joinObj": input_types["joinFn"].output_type})
    tagged_type = tagged_value_type.TaggedValueType(tag_type, inner_type)
    return types.List(tagged_type)


def _all_element_keys(arrs: list[list[dict]]) -> set[str]:
    all_element_keys: set[str] = set([])
    for arr in arrs:
        for element in arr:
            all_element_keys = all_element_keys.union(element.keys())
    return all_element_keys


def _filter_none(arrs: list[typing.Any]) -> list[typing.Any]:
    return [a for a in arrs if a != None]


def _all_join_keys_mapping(
    arrs: list[list[dict]], join_keys: list[list[typing.Any]]
) -> typing.Tuple[set[typing.Any], list[dict[typing.Any, list[typing.Any]]]]:
    all_join_keys: set[typing.Any] = set([])
    join_key_mapping = []
    for arr, keys in zip(arrs, join_keys):
        arr_map: dict = {}
        for k, v in zip(keys, arr):
            if k != None:
                all_join_keys.add(k)
                if k in arr_map:
                    arr_map[k].append(v)
                else:
                    arr_map[k] = [v]
        join_key_mapping.append(arr_map)
    return all_join_keys, join_key_mapping


@op(
    name="joinAll",
    input_type={
        "arrs": types.List(types.optional(types.List(types.TypedDict({})))),
        "joinFn": lambda input_types: types.Function(
            {"row": input_types["arrs"].object_type.object_type}, types.Any()
        ),
    },
    output_type=_join_all_output_type,
)
def join_all(arrs, joinFn, outer: bool):
    # This is a pretty complicated op. See list.ts for the original implementation

    # First, filter out Nones
    arrs = _filter_none(arrs)

    # If nothing remains, simply return.
    if len(arrs) == 0:
        return []

    # Execute the joinFn on each of the arrays
    arrs_keys = [execute_fast.fast_map_fn(arr, joinFn) for arr in arrs]

    # Get the union of all the keys of all the elements
    all_element_keys = _all_element_keys(arrs)
    all_join_keys, join_key_mapping = _all_join_keys_mapping(arrs, arrs_keys)

    # Custom function for create a new row with the new value added
    def _add_val_to_joined_row(joined_row: dict, val: typing.Optional[typing.Any]):
        val = val or {}
        # This is a costly copy...
        copied = {k: [i for i in v] for k, v in joined_row.items()}
        for key in all_element_keys:
            copied[key].append(val.get(key, None))
        return copied

    default_vals = [None] if outer else []
    results = []

    # Each join key may result in several rows
    for k in all_join_keys:
        rows_for_join_key: list[dict] = [{k: [] for k in all_element_keys}]

        # Look through each arr mapping to find the rows for this join key
        for arr_lookup in join_key_mapping:
            # Get the values matching this key for this array
            arr_vals = arr_lookup.get(k, default_vals)

            # For each value, we will append it to every row in the existing list
            new_k_rows = []
            for v in arr_vals:
                for row in rows_for_join_key:
                    new_k_rows.append(_add_val_to_joined_row(row, v))

            # Update the main list
            rows_for_join_key = new_k_rows

        # Tag the elements and add them to the results
        for row in rows_for_join_key:
            row = tag_store.add_tags(box.box(row), {"joinObj": k})
            results.append(row)
    return results


@op(
    name="table-2DProjection",
    input_type={
        "table": types.List(types.optional(types.TypedDict({}))),
        "projectionAlgorithm": types.String(),
        "inputCardinality": types.String(),
        "inputColumnNames": types.List(types.String()),
        "algorithmOptions": types.TypedDict({}),
    },
    output_type=lambda input_types: types.List(
        types.TypedDict(
            {
                "projection": types.TypedDict(
                    {"x": types.Number(), "y": types.Number()}
                ),
                "source": input_types["table"].object_type,
            }
        )
    ),
)
def list_2Dprojection(
    table,
    projectionAlgorithm,
    inputCardinality,
    inputColumnNames,
    algorithmOptions,
):
    inputColumnNames = list(set(inputColumnNames))
    if len(inputColumnNames) == 0 or len(table) < 2:
        projection = [[0, 0] for row in table]
    else:
        embeddings = []
        for row in table:
            if inputCardinality == "single":
                embeddings.append(
                    tag_aware_dict_val_for_escaped_key(row, inputColumnNames[0])
                )
            else:
                embeddings.append(
                    [
                        tag_aware_dict_val_for_escaped_key(row, c)
                        for c in inputColumnNames
                    ]
                )
        np_array_of_embeddings = np.array(embeddings)
        np_projection = projection_utils.perform_2D_projection_with_timeout(
            np_array_of_embeddings,
            projectionAlgorithm,
            algorithmOptions,
        )
        projection = np_projection.tolist()
    return [
        {
            "projection": {
                "x": p[0],
                "y": p[1],
            },
            "source": row,
        }
        for p, row in zip(projection, table)
    ]


@op(
    name="table-projection2D",
    input_type={
        "table": types.List(types.optional(types.TypedDict({}))),
        "projectionAlgorithm": types.String(),
        "inputCardinality": types.String(),
        "inputColumnNames": types.List(types.String()),
        "algorithmOptions": types.TypedDict({}),
    },
    output_type=lambda input_types: types.List(
        types.TypedDict(
            {
                "projection": types.TypedDict(
                    {"x": types.Number(), "y": types.Number()}
                ),
                "source": input_types["table"].object_type,
            }
        )
    ),
)
def list_projection2D(
    table,
    projectionAlgorithm,
    inputCardinality,
    inputColumnNames,
    algorithmOptions,
):
    inputColumnNames = list(set(inputColumnNames))
    if len(inputColumnNames) == 0 or len(table) < 2:
        projection = [[0, 0] for row in table]
    else:
        embeddings = []
        for row in table:
            if inputCardinality == "single":
                embeddings.append(
                    tag_aware_dict_val_for_escaped_key(row, inputColumnNames[0])
                )
            else:
                embeddings.append(
                    [
                        tag_aware_dict_val_for_escaped_key(row, c)
                        for c in inputColumnNames
                    ]
                )
        np_array_of_embeddings = np.array(embeddings)
        np_projection = projection_utils.perform_2D_projection_with_timeout(
            np_array_of_embeddings, projectionAlgorithm, algorithmOptions
        )
        projection = np_projection.tolist()
    return [
        {
            "projection": {
                "x": p[0],
                "y": p[1],
            },
            "source": row,
        }
        for p, row in zip(projection, table)
    ]


@op(
    name="joinToStr",
    input_type={"arr": types.List(types.Any()), "sep": types.String()},
    output_type=types.String(),
)
def join_to_str(arr, sep):
    # This logic matches Weave0 (nulls are treated as empty strings)
    return sep.join([str(i) if i is not None else "" for i in arr])


@op(
    name="contains",
    input_type={"arr": types.List(types.Any()), "element": types.Any()},
    output_type=types.Boolean(),
)
def contains(arr, element):
    return element in arr


@op(
    pure=False,
    output_type=lambda input_types: input_types["arr"],
    name="list-randomlyDownsample",
)
def sample(arr: list[typing.Any], n: int):
    if n < 0:
        raise ValueError("n must be non-negative")
    elif n >= len(arr):
        return arr

    zeros = np.zeros(len(arr), dtype=bool)
    indices = np.random.choice(len(zeros), n, replace=False)
    zeros[indices] = True

    return [arr[i] for i in range(len(arr)) if zeros[i]]


ID_TYPE = types.UnionType(types.String(), types.Int())


def _typeddict_lookup_setter(arr, id, v):
    for i, row in enumerate(arr):
        if row.get("id") == id:
            break
    else:
        return arr
    arr[i] = v
    return arr


@op(
    name="listtypedict-lookup",
    setter=_typeddict_lookup_setter,
    input_type={
        "arr": types.List(types.TypedDict({"id": ID_TYPE})),
        "id": ID_TYPE,
    },
    output_type=getitem_output_type,
)
def typedict_lookup(arr, id):
    for row in arr:
        if row.get("id") == id:
            return row
    return None


def _object_lookup_setter(arr, id, v):
    for i, row in enumerate(arr):
        if row.id == id:
            break
    else:
        return arr
    arr[i] = v
    return arr


@op(
    name="listobject-lookup",
    setter=_object_lookup_setter,
    input_type={
        "arr": types.List(types.ObjectType(id=ID_TYPE)),
        "id": ID_TYPE,
    },
    output_type=getitem_output_type,
)
def object_lookup(arr, id):
    for row in arr:
        if row.id == id:
            return row
    return None


def _cross_product_output_type(input_types):
    obj_type = input_types["obj"]
    if isinstance(obj_type, types.TypedDict):
        new_prop_types = {}
        for k, v in obj_type.property_types.items():
            new_prop_types[k] = v.object_type
        return types.List(
            types.TypedDict(
                {
                    **new_prop_types,
                }
            )
        )
    return types.List(types.Dict(types.String(), types.String()))


@op(render_info={"type": "function"}, output_type=_cross_product_output_type)
def cross_product(obj: dict[str, list]):
    keys = list(obj.keys())
    values = list(obj.values())
    res = []
    for v in itertools.product(*values):
        res.append(dict(zip(keys, v)))
    return res
