import os
import time

import pytest

from weave.legacy.weave import api as weave
from weave.legacy.weave import (
    box,
    context,
    context_state,
    graph,
    ops,
    storage,
    weave_internal,
)
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.ops_domain import table as table_ops

from weave.legacy.tests.util import weavejs_ops

TABLE_TYPES = ["list", "pandas", "sql"]

_loading_builtins_token = context_state.set_loading_built_ins()


@weave.op(
    name="test_table_ops-op_list_table",
    input_type={"n": types.Int()},
    output_type=types.List(types.TypedDict({"a": types.Int(), "b": types.String()})),
)
def op_list_table(n):
    return [{"a": i, "b": str(i)} for i in range(n)]


@weave.op(
    name="test_table_ops-op_list",
    input_type={"n": types.Int()},
    output_type=types.List(types.TypedDict({"a": types.Int(), "b": types.String()})),
)
def op_list(n):
    return [{"a": i, "b": str(i)} for i in range(n)]


context_state.clear_loading_built_ins(_loading_builtins_token)


def get_test_table(table_type):
    if table_type == "list":
        f = ops.local_path(os.path.join("testdata", "cereal.csv"))
        return f.readcsv()
    elif table_type == "pandas":
        f = ops.local_path(os.path.join("testdata", "cereal.csv"))
        return ops.pandasreadcsv(f)
    elif table_type == "sql":
        c = ops.local_sqlconnection("sqlite:///testdata/cereal.db")
        return ops.sqlconnection_table(c, "cereal")


@pytest.mark.parametrize("table_type", TABLE_TYPES)
def test_count(table_type):
    table = get_test_table(table_type)
    expected = 77
    assert weave.use(table.count()) == expected
    assert weave.use(weavejs_ops.count(table)) == expected


@pytest.mark.parametrize("table_type", TABLE_TYPES)
def test_index(table_type):
    table = get_test_table(table_type)
    expected = {
        "name": "100% Bran",
        "mfr": "N",
        "type": "C",
        "calories": 70,
        "protein": 4,
        "fat": 1,
        "sodium": 130,
        "fiber": 10.0,
        "carbo": 5.0,
        "sugars": 6,
        "potass": 280,
        "vitamins": 25,
        "shelf": 3,
        "weight": 1.0,
        "cups": 0.33,
        "rating": 68.402973,
    }
    assert weave.use(table[0]) == expected
    assert weave.use(weavejs_ops.index(table, 0)) == expected


def js_op_mapped_pick(obj, key):
    return weave_internal.make_output_node(
        types.List(obj.type.object_type.property_types[key]),
        "pick",
        {"obj": obj, "key": weave_internal.make_const_node(weave.types.String(), key)},
    )


@pytest.mark.parametrize("table_type", TABLE_TYPES)
def test_pick(table_type):
    table = get_test_table(table_type)
    assert len(weave.use(table.pick("type"))) == 77
    assert len(weave.use(js_op_mapped_pick(table, "type"))) == 77


@pytest.mark.parametrize("table_type", TABLE_TYPES)
def test_filter(table_type):
    table = get_test_table(table_type)
    # Use the lambda passing convention here.
    filter_node = table.filter(lambda row: row["potass"] > 280)
    assert weave.use(filter_node.count()) == 2
    node = weavejs_ops.filter(table, filter_node.from_op.inputs["filterFn"]).count()
    assert weave.use(node) == 2


# WARNING: Separating tests for group by, because
#   pandas removes the group key sometimes, while the
#   other flavors do not.
@pytest.mark.parametrize("table_type", ["pandas"])
def test_groupby(table_type):
    table = get_test_table(table_type)
    groupby_fn = weave_internal.define_fn(
        {"row": weave.types.TypedDict({})}, lambda row: row["type"]
    )
    # TODO: add a pick here to check that it works.
    # TODO: add a pick test for the array case
    # TODO: add some kind of test that relies on type refinement
    expected = [
        "C",
        {
            "name": "100% Bran",
            "mfr": "N",
            "calories": 70,
            "protein": 4,
            "fat": 1,
            "sodium": 130,
            "fiber": 10.0,
            "carbo": 5.0,
            "sugars": 6,
            "potass": 280,
            "vitamins": 25,
            "shelf": 3,
            "weight": 1.0,
            "cups": 0.33,
            "rating": 68.402973,
        },
    ]
    grouped = table.groupby(groupby_fn)
    assert weave.use((grouped[0].groupkey(), grouped[0][0])) == expected


@pytest.mark.parametrize("table_type", ["list", "sql"])
def test_groupby_list(table_type):
    table = get_test_table(table_type)
    grouped = table.groupby(lambda row: row["type"])
    group0 = grouped[0]
    group0key = group0.groupkey()
    group00 = group0[0]
    expected = [
        "C",
        {
            "name": "100% Bran",
            "mfr": "N",
            "calories": 70,
            "protein": 4,
            "fat": 1,
            "sodium": 130,
            "fiber": 10.0,
            "carbo": 5.0,
            "sugars": 6,
            "type": "C",
            "potass": 280,
            "vitamins": 25,
            "shelf": 3,
            "weight": 1.0,
            "cups": 0.33,
            "rating": 68.402973,
        },
    ]
    assert weave.use((group0key, group00)) == expected


@pytest.mark.parametrize("table_type", ["list", "sql"])
def test_groupby_list_weavejs_form(table_type):
    table = get_test_table(table_type)
    groupby_fn = weave_internal.define_fn(
        {"row": table.type.object_type},
        lambda row: graph.OutputNode(
            types.String(),
            "pick",
            {"obj": row, "key": graph.ConstNode(types.String(), "type")},
        ),
    )
    grouped = weavejs_ops.groupby(table, groupby_fn)
    gr0 = weavejs_ops.index(grouped, 0)
    gr00 = weavejs_ops.index(gr0, 0)
    gr00name = weavejs_ops.weavejs_pick(gr00, "name")
    assert weave.use(gr00name) == "100% Bran"


@pytest.mark.parametrize("table_type", TABLE_TYPES)
def test_map(table_type):
    table = get_test_table(table_type)
    map_fn = weave_internal.define_fn(
        {"row": weave.types.TypedDict({})}, lambda row: row["potass"]
    )
    mapped = table.map(map_fn)
    assert weave.use(mapped[0]) == 280


def test_list_returning_op():
    res = weave.use(op_list_table(2))
    expected = [{"a": 0, "b": str(0)}, {"a": 1, "b": str(1)}]
    assert res == expected
    saved = storage.save(res)
    loaded = storage.deref(saved)
    py = storage.to_python(loaded)["_val"]
    assert py == expected


def test_list_map():
    map_fn = weave_internal.define_fn(
        {"row": weave.types.TypedDict({})}, lambda row: row["a"]
    )
    res = weave.use(op_list_table(2).map(map_fn))
    assert res == [0, 1]


def test_list_get_and_op():
    l = weave.use(op_list(2))
    saved = storage.save(l)
    get_node = ops.get(str(saved))

    # The frontend always sends ops.Table.count() (not the same as get_node.count() right
    # now!)
    count_node = weavejs_ops.count(get_node)
    assert weave.use(count_node) == 2


def test_list_save_and_use():
    saved = storage.save([{"a": 5, "b": 6}], "test-list")
    get_node = ops.get(str(saved))
    with context.weavejs_client():
        assert weave.use(get_node) == [{"a": 5, "b": 6}]


def test_groupby_pick():
    items = weave.save([{"a": 5, "b": 6}, {"a": 5, "b": 8}])
    picked = items.groupby(lambda row: row["a"])[0].pick("b")
    assert weave.use(picked.sum() == 14)


def test_rows_type_null():
    type_node = table_ops.Table.rows_type(None)
    assert weave.use(type_node) == types.NoneType()

    type_node = table_ops.Table.rows_type(box.box(None))
    assert weave.use(type_node) == types.NoneType()


def test_sort_timestamp():
    data = [time.time() * 1000 + x for x in range(10)]
    times = weave.save(data)
    timestamps = times.toTimestamp()
    sorted_ts = timestamps.sort(lambda ts: ops.make_list(label=ts), ["asc"])
    assert weave.use(sorted_ts)[0] == weave.use(timestamps[0])

    sorted_ts = sorted_ts.sort(lambda ts: ops.make_list(label=ts), ["desc"])
    assert weave.use(sorted_ts)[0] == weave.use(timestamps[-1])
