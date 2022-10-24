import random

from .. import api as weave
from .. import weave_types as types
from . import list_
from . import dict
from . import number


def test_unnest():
    data = [{"a": [1, 2], "b": "x", "c": [5, 6]}, {"a": [3, 4], "b": "j", "c": [9, 10]}]
    unnested = weave.use(list_.unnest(data))
    # convert to list so pytest prints nice diffs if there is a mismatch
    assert list(unnested) == [
        {"a": 1, "b": "x", "c": 5},
        {"a": 2, "b": "x", "c": 6},
        {"a": 3, "b": "j", "c": 9},
        {"a": 4, "b": "j", "c": 10},
    ]


def test_op_list():
    node = list_.make_list(a=1, b=2, c=3)
    assert types.List(types.Int()).assign_type(node.type)


def test_typeof_groupresult():
    assert types.TypeRegistry.type_of(
        list_.GroupResult([1, 2, 3], "a")
    ) == list_.GroupResultType(types.Int(), types.String())


def test_sequence1():
    l = [
        {"a": 0, "b": 0, "y": "x"},
        {"a": 0, "b": 0, "y": "y"},
        {"a": 0, "b": 1, "y": "x"},
        {"a": 0, "b": 1, "y": "y"},
        {"a": 0, "b": 1, "y": "y"},
        {"a": 1, "b": 1, "y": "y"},
        {"a": 2, "b": 1, "y": "y"},
    ]
    saved = weave.save(l)

    # PanelFacet GroupBy
    groupby1_fn = weave.define_fn(
        {"row": types.TypeRegistry.type_of(l).object_type},
        lambda row: dict.dict_(
            **{
                "a": row["a"],
                "b": row["b"],
            }
        ),
    )
    res = list_.WeaveJSListInterface.groupby(saved, groupby1_fn)

    # Input to PanelPlot
    map1_fn = weave.define_fn({"row": res.type.object_type}, lambda row: row)
    res = list_.WeaveJSListInterface.map(res, map1_fn)

    inner_groupby_fn = weave.define_fn(
        {"row": res.type.object_type.object_type},
        lambda row: dict.dict_(**{"y": row["y"]}),
    )
    map2_fn = weave.define_fn(
        {"row": res.type.object_type},
        lambda row: row.groupby(inner_groupby_fn).map(
            weave.define_fn(
                {
                    "row": list_.GroupResultType(
                        res.type.object_type.object_type,
                        types.TypedDict({"y": types.String()}),
                    )
                },
                lambda row: row.key()["y"],
            )
        ),
    )
    res = list_.WeaveJSListInterface.map(res, map2_fn)
    res = list_.flatten(res)
    res = list_.unique(res)
    assert list(weave.use(res)) == ["x", "y"]


def test_nested_functions():
    rows = weave.save([{"a": [1, 2]}])
    map_fn = weave.define_fn(
        {"row": types.TypedDict({"a": types.List(types.Int())})},
        lambda row: number.numbers_avg(
            row["a"].map(weave.define_fn({"row": types.Int()}, lambda row: row + 1))
        ),
    )
    mapped = rows.map(map_fn)
    assert weave.use(mapped) == [2.5]
