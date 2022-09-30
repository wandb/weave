import pytest
import itertools
import hashlib
import pyarrow as pa
import string
from PIL import Image

from .. import storage
from ..ops_primitives import Number
from .. import api as weave
from .. import ops
from .. import artifacts_local
from . import arrow
from .. import weave_types as types
from .. import weave_internal
from .. import context_state

_loading_builtins_token = context_state.set_loading_built_ins()
# T in `conftest::pre_post_each_test` we set a custom artifact directory for each test for isolation
# Puting this import in the context allows the test execution to access these ops
@weave.type()
class Point2:
    x: float
    y: float

    @weave.op()
    def get_x(self) -> float:
        return self.x


context_state.clear_loading_built_ins(_loading_builtins_token)


def simple_hash(n, b):
    return int.from_bytes(hashlib.sha256(str(n).encode()).digest(), "little") % b


def create_arrow_data(n_rows, n_extra_cols=0, images=False):
    inner_count = int(n_rows / 25)
    base_im = Image.linear_gradient("L")
    x_choices = string.ascii_lowercase
    extra_cols = [chr(ord("a") + i) for i in range(n_extra_cols)]
    ims = []
    for i, (rotate, shear, _) in enumerate(
        itertools.product(range(5), range(5), range(inner_count))
    ):
        im = {
            "rotate": rotate,
            "shear": shear,
            "x": x_choices[simple_hash(i**13, 3)],
            "y": simple_hash(i, 10),
        }
        if images:
            im["image"] = base_im.rotate(rotate * 4).transform(
                (256, 256), Image.AFFINE, (1, shear / 10, 0, 0, 1, 0), Image.BICUBIC
            )
        for j, col in enumerate(extra_cols):
            im[col] = x_choices[simple_hash(i * 13**j, 11)]
        ims.append(im)
    arr = arrow.to_arrow(ims)
    return storage.save(arr)


def test_groupby_index_count():
    ref = create_arrow_data(1000)
    node = (
        weave.get(ref)
        .groupby(lambda row: ops.dict_(rotate=row["rotate"], shear=row["shear"]))[1]
        .count()
    )
    assert weave.use(node) == 40


def test_map_scalar_map():
    ref = create_arrow_data(1000)

    node = weave.get(ref).map(lambda row: row["y"] + 1).map(lambda row: row + 9)
    assert weave.use(node[0]) == 15
    assert weave.use(node[4]) == 17


def test_complicated():
    ref = create_arrow_data(1000)
    node = (
        weave.get(ref)
        .groupby(lambda row: ops.dict_(rotate=row["rotate"], shear=row["shear"]))
        .map(lambda row: row.groupby(lambda row: row["y"]))
        .dropna()
        .count()
    )
    assert weave.use(node) == 25


def test_table_string_histogram():
    ref = create_arrow_data(1000)
    node = (
        weave.get(ref)
        .groupby(lambda row: ops.dict_(rotate=row["rotate"]))[0]
        .pick("x")
        .groupby(lambda row: ops.dict_(row=row))
        .map(lambda row: row.key().merge(ops.dict_(count=row.count())))
        .count()
    )
    assert weave.use(node) == 3


def test_custom_types():
    data_node = arrow.to_arrow(
        [
            {"a": 5, "im": Image.linear_gradient("L").rotate(0)},
            {"a": 6, "im": Image.linear_gradient("L").rotate(4)},
        ]
    )
    assert weave.use(data_node[0]["im"].width()) == 256

    assert weave.use(data_node.map(lambda row: row["im"].width())).to_pylist() == [
        256,
        256,
    ]


def test_custom_saveload():
    data = arrow.to_arrow(
        [
            {"a": 5, "im": Image.linear_gradient("L").rotate(0)},
            {"a": 6, "im": Image.linear_gradient("L").rotate(4)},
        ]
    )
    ref = storage.save(data)
    data2 = storage.get(str(ref))
    print("data2", data2._artifact)
    assert weave.use(data2[0]["im"].width()) == 256


# @pytest.mark.skip()
def test_custom_groupby():
    data = arrow.to_arrow(
        [
            {"a": 5, "im": Image.linear_gradient("L").rotate(0)},
            {"a": 6, "im": Image.linear_gradient("L").rotate(4)},
        ]
    )

    assert (
        weave.use(
            data.groupby(lambda row: ops.dict_(a=row["a"]))[0]
            .pick("im")
            .offset(0)[0]
            .width()
        )
        == 256
    )


def test_custom_groupby_intermediate_save():
    data = arrow.to_arrow(
        [
            {"a": 5, "im": Image.linear_gradient("L").rotate(0)},
            {"a": 6, "im": Image.linear_gradient("L").rotate(4)},
        ]
    )
    node = data.groupby(lambda row: ops.dict_(a=row["a"]))[0]
    saved_node = weave.save(node, "test_custom_groupby_intermediate_save")
    weave.use(saved_node)
    loaded_node = ops.get(
        f"local-artifact://{artifacts_local.local_artifact_dir()}/test_custom_groupby_intermediate_save/latest"
    )
    assert weave.use(loaded_node.pick("im").offset(0)[0].width()) == 256


def test_map_array():
    data = arrow.to_arrow([1, 2, 3])
    assert weave.use(data.map(lambda i: i + 1)).to_pylist() == [2, 3, 4]


def test_map_typeddict():
    data = arrow.to_arrow([{"a": 1, "b": 2}, {"a": 3, "b": 5}])
    assert weave.use(data.map(lambda row: row["a"])).to_pylist() == [1, 3]


def test_map_object():
    data = arrow.to_arrow([Point2(1, 2), Point2(5, 6)])
    assert weave.use(data.map(lambda row: row.get_x())).to_pylist() == [1, 5]


@pytest.mark.skip("not working yet")
def test_map_typeddict_object():
    data = arrow.to_arrow([{"a": 0, "p": Point2(1, 2)}, {"a": 3, "p": Point2(9, 12)}])
    assert weave.use(data.map(lambda row: row["p"])).to_pylist() == []


def test_arrow_list_of_ref_to_item_in_list():
    l = [{"a": 5, "b": 6}, {"a": 7, "b": 9}]
    l_node = weave.save(l, "my-l")

    list_dict_with_ref = arrow.to_arrow([{"c": l_node[0]["a"]}, {"c": l_node[1]["a"]}])
    d_node = weave.save(list_dict_with_ref, "my-dict_with_ref")

    assert weave.use(d_node[0]["c"] == 5) == True
    assert weave.use(d_node[1]["c"] == 7) == True


# TODO: move to generic test as Weave types test.
def test_arrow_list_assign():
    assert (
        arrow.ArrowWeaveListNumberType().assign_type(
            arrow.ArrowWeaveListType(weave.types.Number())
        )
        != weave.types.Invalid()
    )


def test_arrow_unnest():
    data = arrow.to_arrow([{"a": [1, 2, 3], "b": "c"}, {"a": [4, 5, 6], "b": "d"}])
    assert weave.type_of(data) == arrow.ArrowWeaveListType(
        types.TypedDict({"a": types.List(types.Int()), "b": types.String()})
    )
    unnest_node = data.unnest()
    assert unnest_node.type == arrow.ArrowWeaveListType(
        types.TypedDict({"a": types.Int(), "b": types.String()})
    )
    assert weave.use(data.unnest()).to_pylist() == [
        {"a": 1, "b": "c"},
        {"a": 2, "b": "c"},
        {"a": 3, "b": "c"},
        {"a": 4, "b": "d"},
        {"a": 5, "b": "d"},
        {"a": 6, "b": "d"},
    ]


def test_arrow_concat_arrow_weave_list():

    # test concatenating two arrow weave lists that contain chunked arrays of the same type
    ca1 = pa.chunked_array([[1, 2], [3, 4]])
    ca2 = pa.compute.add(ca1, 1)
    awl1 = arrow.ArrowWeaveList(ca1)
    awl2 = arrow.ArrowWeaveList(ca2)
    result = awl1.concatenate(awl2)

    assert result._arrow_data.chunks == ca1.chunks + ca2.chunks

    # test concatenating two arrow weave lists that contain tables of the same type
    t1 = pa.table([[1, 2], [3, 4]], names=["col1", "col2"])
    t2 = pa.table([[2, 3], [4, 5]], names=["col1", "col2"])
    awl1 = arrow.ArrowWeaveList(t1)
    awl2 = arrow.ArrowWeaveList(t2)
    result = awl1.concatenate(awl2)

    assert result._arrow_data == pa.concat_tables([t1, t2])

    # test concatenating two arrow weave lists that contain chunked arrays of different types
    ca1 = pa.chunked_array([[1, 2], [3, 4]])
    ca2 = pa.chunked_array([["b", "c"], ["e", "d"]])
    awl1 = arrow.ArrowWeaveList(ca1)
    awl2 = arrow.ArrowWeaveList(ca2)

    with pytest.raises(ValueError):
        awl1.concatenate(awl2)

    # test concatenating two arrow weave lists that contain tables of different types
    t1 = pa.table([[1, 2], [3, 4]], names=["col1", "col2"])
    t2 = pa.table([["b", "c"], ["e", "d"]], names=["col1", "col2"])
    awl1 = arrow.ArrowWeaveList(t1)
    awl2 = arrow.ArrowWeaveList(t2)

    with pytest.raises(ValueError):
        awl1.concatenate(awl2)


def test_arrow_weave_list_groupby_struct_type_table():

    table = pa.Table.from_pylist(
        [{"d": {"a": 1, "b": 2}, "c": 1}, {"d": {"a": 3, "b": 4}, "c": 2}]
    )
    awl = arrow.ArrowWeaveList(table)

    def group_func_body(row):
        return ops.dict_(**{"d": row["d"]})

    # note: access more than 1 level deep is broken, should work, fix
    # def group_func_body(row):
    #    return ops.dict_(**{"d.a": row["d"]["a"]})

    group_func = weave_internal.define_fn({"row": awl.object_type}, group_func_body)
    grouped = awl.groupby(group_func)
    assert weave.use(grouped[0])._arrow_data.to_pylist() == [
        {"d": {"a": 1, "b": 2}, "c": 1}
    ]


def test_arrow_weave_list_groupby_struct_chunked_array_type():
    ref = create_arrow_data(1000)

    # chunkedarray is used when there are two levels of nesting
    node = (
        weave.get(ref)
        .groupby(lambda row: ops.dict_(rotate=row["rotate"], shear=row["shear"]))
        .map(lambda row: row.groupby(lambda row: row["y"]))
        .dropna()[0][0]
    )

    assert (
        weave.use(node)._arrow_data.to_pylist()
        == [{"rotate": 0, "shear": 0, "x": "a", "y": 5}] * 5
    )


@pytest.mark.parametrize(
    "name,weave_func,expected_output",
    [
        ("add", lambda x: x + 2, [3.0, 4.0, 5.0]),
        ("add-vec", lambda x: x + x, [2.0, 4.0, 6.0]),
        ("subtract", lambda x: x - 1, [0.0, 1.0, 2.0]),
        ("multiply", lambda x: x * 2, [2.0, 4.0, 6.0]),
        ("divide", lambda x: x / 2, [0.5, 1.0, 1.5]),
        ("pow", lambda x: x**2, [1.0, 4.0, 9.0]),
        ("ne", lambda x: x != 2, [True, False, True]),
        ("eq", lambda x: x == 2, [False, True, False]),
        ("gt", lambda x: x > 2, [False, False, True]),
        ("lt", lambda x: x < 2, [True, False, False]),
        ("ge", lambda x: x >= 2, [False, True, True]),
        ("le", lambda x: x <= 2, [True, True, False]),
        ("neg", lambda x: -x, [-1.0, -2.0, -3.0]),
    ],
)
def test_arrow_vectorizer_number_ops(name, weave_func, expected_output):
    l = weave.save(arrow.to_arrow([1.0, 2.0, 3.0]))

    fn = weave_internal.define_fn({"x": weave.types.Float()}, weave_func).val

    vec_fn = arrow.vectorize(fn)

    # TODO:  make it nicer to call vec_fn, we shouldn't need to jump through hoops here
    called = weave_internal.call_fn(vec_fn, {"x": l})

    assert weave.use(called).to_pylist() == expected_output


@pytest.mark.parametrize(
    "name,weave_func,expected_output",
    [
        ("floor", lambda x: Number.floor(x), [1.0, 2.0, 3.0]),
        ("ceil", lambda x: Number.ceil(x), [2.0, 3.0, 4.0]),
    ],
)
def test_arrow_floor_ceil_vectorized(name, weave_func, expected_output):
    l = weave.save(arrow.to_arrow([1.1, 2.5, 3.9]))
    fn = weave_internal.define_fn({"x": weave.types.Float()}, weave_func).val
    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"x": l})
    assert weave.use(called).to_pylist() == expected_output
