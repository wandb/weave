import pytest
import itertools
import hashlib
import pyarrow as pa
import random
import string
from PIL import Image

from .. import storage
from .. import api as weave
from .. import ops


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
    arr = storage.to_arrow(ims)
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
    data_node = storage.to_arrow(
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
    data = storage.to_arrow(
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
    data = storage.to_arrow(
        [
            {"a": 5, "im": Image.linear_gradient("L").rotate(0)},
            {"a": 6, "im": Image.linear_gradient("L").rotate(4)},
        ]
    )
    print(
        "TYPE",
        data.groupby(lambda row: ops.dict_(a=row["a"]))[0].pick("im").offset(0).type,
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


def test_map_array():
    data = storage.to_arrow([1, 2, 3])
    assert weave.use(data.map(lambda i: i + 1)).to_pylist() == [2, 3, 4]


def test_map_typeddict():
    data = storage.to_arrow([{"a": 1, "b": 2}, {"a": 3, "b": 5}])
    assert weave.use(data.map(lambda row: row["a"])).to_pylist() == [1, 3]


@weave.type()
class Point2:
    x: float
    y: float

    @weave.op()
    def get_x(self) -> float:
        return self.x


def test_map_object():
    data = storage.to_arrow([Point2(1, 2), Point2(5, 6)])
    assert weave.use(data.map(lambda row: row.get_x())).to_pylist() == [1, 5]


@pytest.mark.skip("not working yet")
def test_map_typeddict_object():
    data = storage.to_arrow([{"a": 0, "p": Point2(1, 2)}, {"a": 3, "p": Point2(9, 12)}])
    assert weave.use(data.map(lambda row: row["p"])).to_pylist() == []
