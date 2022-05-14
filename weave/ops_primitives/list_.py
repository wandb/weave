import pandas
import typing
from .. import weave_types as types
from ..api import op, mutation, weave_class, OpVarArgs
from .. import weave_internal
from .. import graph
from .. import errors


@weave_class(weave_type=types.List)
class List:
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
        output_type=lambda input_types: input_types["self"].object_type,
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
        output_type=types.Any(),
    )
    def pick(self, key):
        return [row.get(key) for row in self]

    @op(
        input_type={"self": types.List(types.Any()), "filter_fn": types.Any()},
        output_type=lambda input_types: input_types["self"],
    )
    def filter(self, filter_fn):
        calls = []
        for row in self:
            calls.append(
                weave_internal.call_fn(
                    filter_fn, {"row": graph.ConstNode(types.Any(), row)}
                )
            )
        result = []
        for row, keep in zip(self, weave_internal.use_internal(calls)):
            if keep:
                result.append(row)
        return result

    @op(
        input_type={"self": types.List(types.Any()), "map_fn": types.Any()},
        output_type=lambda input_types: input_types["self"],
    )
    def map(self, map_fn):
        calls = []
        for i, row in enumerate(self):
            calls.append(
                weave_internal.call_fn(
                    map_fn,
                    {
                        "row": graph.ConstNode(types.Any(), row),
                        "index": graph.ConstNode(types.Number(), i),
                    },
                )
            )
        result = weave_internal.use_internal(calls)
        return result

    @op(
        input_type={"self": types.List(types.Any()), "group_by_fn": types.Any()},
        output_type=lambda input_types: types.List(
            GroupResultType(input_types["self"])
        ),
    )
    def groupby(self, group_by_fn):
        calls = []
        for row in self:
            calls.append(
                weave_internal.call_fn(
                    group_by_fn, {"row": graph.ConstNode(types.Any(), row)}
                )
            )
        result = {}
        for row, group_key_items in zip(self, weave_internal.use_internal(calls)):
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
        # So lame, we can't use slice because sometimes we have an ArrowArrayTable here
        # TODO: fix
        res = []
        for i in range(offset, len(arr)):
            res.append(arr[i])
        return res

    @op(
        name="limit",
        input_type={"arr": types.List(types.Any()), "limit": types.Number()},
        output_type=lambda input_types: input_types["arr"],
    )
    def limit(arr, limit):
        # So lame, we can't use slice because sometimes we have an ArrowArrayTable here
        # TODO: fix
        res = []
        if limit >= len(arr):
            limit = len(arr)
        for i in range(limit):
            res.append(arr[i])
        return res
        # return arr[:limit]


class GroupResultType(types.ObjectType):
    name = "groupresult"

    type_vars = {"list": types.List(types.Any()), "key": types.Any()}

    def __init__(self, list=types.List(types.Any()), key=types.Any()):
        self.list = list
        self.key = key

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

    @op(
        name="group-groupkey",
        input_type={"obj": GroupResultType()},
        output_type=types.Any(),
    )
    def key(obj):
        return obj.key

    @op(output_type=types.Any())
    def pick(self, key: str):
        return List.pick.resolve_fn(self.list, key)

    @op()
    def count(self) -> int:
        return len(self.list)

    @op(output_type=group_result_index_output_type)
    def __getitem__(self, index: int):
        return List.__getitem__.resolve_fn(self.list, index)


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


@op(
    name="flatten", input_type={"arr": types.List(types.Any())}, output_type=types.Any()
)
def flatten(arr):
    # TODO: probably doesn't match js implementation
    result = []
    for row in arr:
        if isinstance(row, list):
            for o in row:
                result.append(o)
        else:
            result.append(row)
    return result


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
    return pandas.DataFrame(arr).explode(list_cols).to_dict("records")


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
        output_type = object_type.value_type
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


class WeaveJSListInterface:
    @op(name="count")
    def count(arr: list[typing.Any]) -> int:  # type: ignore
        type_class = types.TypeRegistry.type_class_of(arr)
        return type_class.NodeMethodsClass.count.resolve_fn(arr)

    @op(name="index", output_type=index_output_type)
    def index(arr: list[typing.Any], index: int):  # type: ignore
        type_class = types.TypeRegistry.type_class_of(arr)
        return type_class.NodeMethodsClass.__getitem__.resolve_fn(arr, index)

    # This should not actually be part of the list interface, as its
    # only valid when contained items are lists. However, this is the
    # best place to adapt to frontend behavior, which expects a single
    # pick op that does mapping as well as TypedDict lookups.
    @op(
        name="pick",
        input_type={
            "obj": types.UnionType(
                types.TypedDict({}), types.List(types.TypedDict({}))
            ),
            "key": types.String(),
        },
        output_type=pick_output_type,
    )
    def pick(obj, key):  # type: ignore
        type_class = types.TypeRegistry.type_class_of(obj)
        return type_class.NodeMethodsClass.pick.resolve_fn(obj, key)

    @op(name="filter", output_type=lambda input_types: input_types["arr"])
    def filter(arr: list[typing.Any], filterFn: typing.Any):  # type: ignore
        type_class = types.TypeRegistry.type_class_of(arr)
        return type_class.NodeMethodsClass.filter.resolve_fn(arr, filterFn)

    @op(name="map", output_type=types.Any())
    def map(arr: list[typing.Any], mapFn: typing.Any):  # type: ignore
        type_class = types.TypeRegistry.type_class_of(arr)
        return type_class.NodeMethodsClass.map.resolve_fn(arr, mapFn)

    @op(
        name="groupby",
        output_type=lambda input_types: types.List(
            GroupResultType(types.List(input_types["arr"].object_type), types.Any())
        ),
    )
    def groupby(arr: list[typing.Any], groupByFn: typing.Any):  # type: ignore
        type_class = types.TypeRegistry.type_class_of(arr)
        try:
            return type_class.NodeMethodsClass.groupby.resolve_fn(arr, groupByFn)
        except AttributeError:
            groupby_res = List.groupby.resolve_fn(arr, groupByFn)
            return groupby_res


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
