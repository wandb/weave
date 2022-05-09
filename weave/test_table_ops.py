import os
import pytest

from . import api as weave
from . import weave_types as types
from . import ops
from . import storage
from . import context

TABLE_TYPES = ["list", "pandas", "sql"]


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
    assert weave.use(ops.WeaveJSListInterface.count(table)) == expected


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
    assert weave.use(ops.WeaveJSListInterface.index(table, 0)) == expected


@pytest.mark.parametrize("table_type", TABLE_TYPES)
def test_pick(table_type):
    table = get_test_table(table_type)
    assert len(weave.use(table.pick("type"))) == 77
    assert len(weave.use(ops.WeaveJSListInterface.pick(table, "type"))) == 77


@pytest.mark.parametrize("table_type", TABLE_TYPES)
def test_filter(table_type):
    table = get_test_table(table_type)
    filter_fn = weave.define_fn(
        {"row": weave.types.TypedDict({})}, lambda row: row["potass"] > 280
    )
    assert weave.use(table.filter(filter_fn).count()) == 2
    assert weave.use(ops.WeaveJSListInterface.filter(table, filter_fn).count()) == 2


# WARNING: Separating tests for group by, because
#   pandas removes the group key sometimes, while the
#   other flavors do not.
@pytest.mark.parametrize("table_type", ["pandas"])
def test_groupby(table_type):
    table = get_test_table(table_type)
    groupby_fn = weave.define_fn(
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
    assert weave.use((grouped[0].key(), grouped[0][0])) == expected
    grouped_js = ops.WeaveJSListInterface.groupby(table, groupby_fn)
    assert weave.use((grouped_js[0].key(), grouped_js[0][0])) == expected


@pytest.mark.parametrize("table_type", ["list", "sql"])
def test_groupby_list(table_type):
    table = get_test_table(table_type)
    groupby_fn = weave.define_fn(
        {"row": weave.types.TypedDict({})}, lambda row: row["type"]
    )
    grouped = table.groupby(groupby_fn)
    group0 = grouped[0]
    group0key = group0.key()
    group00 = group0[0]
    assert weave.use((group0key, group00)) == [
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


@pytest.mark.parametrize("table_type", TABLE_TYPES)
def test_map(table_type):
    table = get_test_table(table_type)
    map_fn = weave.define_fn(
        {"row": weave.types.TypedDict({})}, lambda row: row["potass"]
    )
    mapped = table.map(map_fn)
    assert weave.use(mapped[0]) == 280


@weave.op(
    name="test_table_ops-op_list_table",
    input_type={"n": types.Int()},
    output_type=types.List(types.TypedDict({"a": types.Int(), "b": types.String()})),
)
def op_list_table(n):
    return [{"a": i, "b": str(i)} for i in range(n)]


def test_list_returning_op():
    res = weave.use(op_list_table(2))
    expected = [{"a": 0, "b": str(0)}, {"a": 1, "b": str(1)}]
    assert res == expected
    saved = storage.save(res)
    loaded = storage.deref(saved)
    py = storage.to_python(loaded)["_val"]
    assert py == expected


def test_list_map():
    map_fn = weave.define_fn({"row": weave.types.TypedDict({})}, lambda row: row["a"])
    res = weave.use(op_list_table(2).map(map_fn))
    assert res == [0, 1]


@weave.op(
    name="test_table_ops-op_list",
    input_type={"n": types.Int()},
    output_type=types.List(types.TypedDict({"a": types.Int(), "b": types.String()})),
)
def op_list(n):
    return [{"a": i, "b": str(i)} for i in range(n)]


def test_list_get_and_op():
    l = weave.use(op_list(2))
    saved = storage.save(l)
    get_node = ops.get(str(saved))

    # The frontend always sends ops.Table.count() (not the same as get_node.count() right
    # now!)
    count_node = ops.WeaveJSListInterface.count(get_node)
    assert weave.use(count_node) == 2


def test_list_save_and_use():
    saved = storage.save([{"a": 5, "b": 6}], "test-list")
    with context.weavejs_client():
        assert weave.use(ops.get(str(saved))) == [{"a": 5, "b": 6}]
