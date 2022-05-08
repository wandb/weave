import typing
from .. import weave_types as types
from ..api import op, mutation, weave_class
from .. import weave_internal
from .. import graph


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
        name="list-getitem",
        input_type={"self": types.List(types.Any()), "index": types.Int()},
        output_type=lambda input_types: input_types["self"].object_type,
    )
    def __getitem__(self, index):
        try:
            return self.__getitem__(index)
        except IndexError:
            return None

    @op(
        name="list-pick",
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
        name="list-filter",
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
        name="list-map",
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
        name="list-groupby",
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


class GroupResultType(types.ObjectType):
    name = "groupresult2"

    type_vars = {"list": types.List(types.Any())}

    def __init__(self, list):
        self.list = list

    def property_types(self):
        return {"key": types.String(), "list": self.list}


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
        input_type={"obj": GroupResultType(types.List(types.Any()))},
        output_type=types.Any(),
    )
    def key(obj):
        return obj.key

    @op(
        name="group-getitem",
        input_type={
            "self": GroupResultType(types.List(types.Any())),
            "index": types.Int(),
        },
        output_type=group_result_index_output_type,
    )
    def __getitem__(self, index):
        return List.__getitem__.op_def.resolve_fn(self.list, index)


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
    name="limit",
    input_type={"arr": types.List(types.Any()), "limit": types.Number()},
    output_type=types.Any(),
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
    if isinstance(arr, Table):
        return arr.unnest()
    return arr


def index_output_type(input_types):
    # THIS IS NO GOOD
    # TODO: need to fix Const type so we don't need this.
    self_type = input_types["arr"]
    if isinstance(self_type, types.Const):
        return self_type.val_type.object_type
    else:
        return self_type.object_type


class WeaveJSListInterface:
    @op(name="count")
    def count(arr: list[typing.Any]) -> int:  # type: ignore
        type_class = types.TypeRegistry.type_class_of(arr)
        return type_class.NodeMethodsClass.count.op_def.resolve_fn(arr)

    @op(name="index", output_type=index_output_type)
    def index(arr: list[typing.Any], index: int):  # type: ignore
        type_class = types.TypeRegistry.type_class_of(arr)
        return type_class.NodeMethodsClass.__getitem__.op_def.resolve_fn(arr, index)
