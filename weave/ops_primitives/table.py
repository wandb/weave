from ..api import op, weave_class, mutation
from .. import weave_types as types
from .. import weave_internal
from .. import graph


@weave_class(weave_type=types.List)
class List(list):
    @op(
        name="index",
        input_type={"arr": types.List(types.Any()), "index": types.Int()},
        output_type=lambda input_types: input_types["arr"].object_type,
    )
    def __getitem__(arr, index):
        try:
            return arr[index]
        except IndexError:
            return None


@weave_class(weave_type=types.Table)
class Table:
    @op(
        name="count",
        input_type={"arr": types.List(types.Any())},
        output_type=types.Number(),
    )
    def count(arr):
        return arr.count()  # delegate to subclass

    @mutation
    def __setitem__(self, k, v):
        self.list[k] = v
        return self

    @op(
        setter=__setitem__,
        name="index",
        input_type={"arr": types.List(types.Any()), "index": types.Number()},
        output_type=lambda input_types: input_types["arr"].object_type,
    )
    def __getitem__(arr, index):
        try:
            return arr.index(index)
        except ValueError:
            # UGHHH FIX
            # TODO
            return arr.__getitem__(index)

    @op(
        name="offset",
        input_type={"arr": types.List(types.Any())},
        output_type=lambda x: x,
    )
    def offset(arr):
        # TODO: not implemented
        return arr

    @op(
        name="limit",
        input_type={"arr": types.List(types.Any())},
        output_type=lambda x: x,
    )
    def limit(arr):
        # TODO: not implemented
        return arr

    # note, this isn't quite true...
    #    if we have Run[], PanelTable can still render,
    #    but it doesn't have pick
    # it has the set of ops available for whatever object is contained in the
    #    array
    # pandas and sql always contain object looking objects.
    #
    # Hmm, I think there is a nicer way to implement mapped operations though??

    def pick(arr, key):
        # TODO: This is not right, need to figure out mapped ops. But it works
        # for the moment
        return arr.pick(key)

    @op(
        name="map",
        input_type={"arr": types.List(types.Any()), "mapFn": types.Any()},
        output_type=types.Table(),
    )
    def map(arr, mapFn):
        return arr.map(mapFn)

    @op(
        name="filter",
        input_type={"arr": types.List(types.Any()), "filterFn": types.Any()},
        output_type=types.Table(),
    )
    def filter(arr, filterFn):
        return arr.filter(filterFn)

    @op(
        name="groupby",
        input_type={"arr": types.List(types.Any()), "groupByFn": types.Any()},
        output_type=lambda input_types: types.Table(
            GroupResultType(input_types["arr"])
        ),
    )
    def groupby(arr, groupByFn):
        return arr.groupby(groupByFn)

    def unnest(self):
        raise NotImplementedError


class ListTableType(types.ObjectType):
    name = "list_table"

    type_vars = {"list": types.List(types.Any())}

    def __init__(self, list):
        self.list = list

    # Make this behave like a list type.
    # TODO: is this a reasonable thing to do?
    @property
    def object_type(self):
        return self.list.object_type

    def property_types(self):
        return {
            "list": self.list,
        }


@weave_class(weave_type=ListTableType)
class ListTable(Table):
    def __init__(self, list):
        self.list = list

    def count(self):
        return len(self.list)

    def index(self, index):
        try:
            return self.list[index]
        except IndexError:
            return None

    def pick(self, key):
        # TODO: Totally not right but it'll work for now. Need to figure out
        # mapped ops
        return [v.get(key) for v in self.list]

    def map(self, mapFn):
        calls = []
        for i, row in enumerate(self.list):
            calls.append(
                weave_internal.call_fn(
                    mapFn,
                    {
                        "row": graph.ConstNode(types.Any(), row),
                        "index": graph.ConstNode(types.Number(), i),
                    },
                )
            )
        result = weave_internal.use_internal(calls)
        return ListTable(result)

    def filter(self, filterFn):
        calls = []
        for row in self.list:
            calls.append(
                weave_internal.call_fn(
                    filterFn, {"row": graph.ConstNode(types.Any(), row)}
                )
            )
        result = []
        for row, keep in zip(self.list, weave_internal.use_internal(calls)):
            if keep:
                result.append(row)
        return ListTable(result)

    def groupby(self, groupByFn):
        calls = []
        for row in self.list:
            calls.append(
                weave_internal.call_fn(
                    groupByFn, {"row": graph.ConstNode(types.Any(), row)}
                )
            )
        result = {}
        for row, group_key_items in zip(self.list, weave_internal.use_internal(calls)):
            import json

            group_key_s = json.dumps(group_key_items)
            if group_key_s not in result:
                result[group_key_s] = (group_key_items, [])
            result[group_key_s][1].append(row)
        # TODO: relying on dict ordering???
        grs = []
        for group_result in result.values():
            grs.append(GroupResult(group_result[1], group_result[0]))
        return ListTable(grs)

    def unnest(self):
        # HACK return the raw list because the frontend expects it
        # TODO: probably need to change the frontend?
        return self.list
        # TODO
        return ListTable(self.list)


ListTableType.instance_classes = ListTable
ListTableType.instance_class = ListTable


class GroupResultType(ListTableType):
    name = "groupresult"

    def property_types(self):
        return {"key": types.String(), "list": self.list}


@weave_class(weave_type=GroupResultType)
class GroupResult(ListTable):
    def __init__(self, list, key):
        super(GroupResult, self).__init__(list)
        self.key = key

    @op(
        name="group-groupkey",
        input_type={"obj": types.List(types.Any())},
        output_type=types.Any(),
    )
    def key(obj):
        return obj.key


GroupResultType.instance_classes = GroupResult
GroupResultType.instance_class = GroupResult


@op(
    name="list-indexCheckpoint",
    input_type={"arr": types.List(types.Any())},
    output_type=types.Any(),
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
