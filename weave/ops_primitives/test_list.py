import random

from .. import api as weave
from .. import weave_types as types
from .. import box
from . import list_
from . import dict
from . import number
from .. import weave_internal
from ..tests import weavejs_ops
from ..language_features.tagging import make_tag_getter_op, tag_store, tagged_value_type


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
    res = weavejs_ops.groupby(saved, groupby1_fn)

    # Input to PanelPlot
    map1_fn = weave.define_fn({"row": res.type.object_type}, lambda row: row)
    res = weavejs_ops.map(res, map1_fn)

    inner_groupby_fn = weave.define_fn(
        {"row": res.type.object_type.object_type},
        lambda row: dict.dict_(**{"y": row["y"]}),
    )
    map2_fn = weave.define_fn(
        {"row": res.type.object_type},
        lambda row: row.groupby(inner_groupby_fn).map(
            weave.define_fn(
                {
                    "row": tagged_value_type.TaggedValueType(
                        types.TypedDict(
                            {"groupKey": types.TypedDict({"y": types.String()})}
                        ),
                        res.type.object_type,
                    )
                },
                lambda row: row.groupkey()["y"],
            )
        ),
    )
    res = weavejs_ops.map(res, map2_fn)
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


def test_concat():
    list_node_1 = list_.make_list(a=1, b=2, c=3)
    list_node_2 = list_.make_list(a=10, b=20, c=30)
    list_node_3 = list_.make_list(a=list_node_1, b=list_node_2)
    concat_list = list_node_3.concat()
    assert weave.use(concat_list) == [1, 2, 3, 10, 20, 30]


def test_nullable_concat():
    list_node_1 = list_.make_list(a=1, b=2, c=3)
    list_node_2 = list_.make_list(a=10, b=20, c=30)
    list_node_3 = list_.make_list(a=list_node_1, b=list_node_2, c=weave.save(None))
    concat_list = list_node_3.concat()
    assert weave.use(concat_list) == [1, 2, 3, 10, 20, 30]


def test_mapeach():
    row_node = list_.make_list(a=1, b=2, c=3)
    two_d_list_node = list_.make_list(a=row_node, b=row_node, c=row_node)
    result = list_.map_each(two_d_list_node, lambda row: row + 1)
    assert result.type == types.List(types.List(types.Number()))
    assert weave.use(result) == [[2, 3, 4], [2, 3, 4], [2, 3, 4]]


def test_mapeach_single():
    row_node = list_.make_list(a=1, b=2, c=3)
    item = row_node[0]
    result = list_.map_each(item, lambda row: row + 1)
    assert result.type == types.Number()
    assert weave.use(result) == 2


def test_mapeach_tagged():
    raw_data = [[i + 3 * j for i in [2, 3, 4]] for j in [0, 1, 2]]
    for i, row in enumerate(raw_data):
        for j, value in enumerate(row):
            raw_data[i][j] = tag_store.add_tags(box.box(value), {"row": i, "col": j})
        raw_data[i] = tag_store.add_tags(box.box(raw_data[i]), {"row": i})
    raw_data = tag_store.add_tags(box.box(raw_data), {"tag": "top"})
    two_d_list_node = weave.save(raw_data)

    result = list_.map_each(two_d_list_node, lambda row: row + 1)

    expected_type = tagged_value_type.TaggedValueType(
        types.TypedDict({"tag": types.String()}),
        types.List(
            tagged_value_type.TaggedValueType(
                types.TypedDict({"row": types.Int()}),
                types.List(
                    tagged_value_type.TaggedValueType(
                        types.TypedDict({"row": types.Int(), "col": types.Int()}),
                        types.Number(),
                    )
                ),
            )
        ),
    )

    assert expected_type.assign_type(result.type)
    assert weave.use(result) == [[i + 3 * j for i in [3, 4, 5]] for j in [0, 1, 2]]

    tag_getter_op_top = make_tag_getter_op.make_tag_getter_op("tag", types.String())
    tag_getter_op_row = make_tag_getter_op.make_tag_getter_op("row", types.Int())
    tag_getter_op_col = make_tag_getter_op.make_tag_getter_op("col", types.Int())

    assert weave.use(tag_getter_op_top(result)) == "top"
    for i in range(3):
        assert weave.use(tag_getter_op_row(result[i])) == i
        for j in range(3):
            assert weave.use(tag_getter_op_row(result[i][j])) == i
            assert weave.use(tag_getter_op_col(result[i][j])) == j
