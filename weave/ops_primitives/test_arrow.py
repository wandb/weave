import itertools
import hashlib
import pyarrow as pa
import random
from PIL import Image

from .. import storage
from .. import api as weave
from .. import ops


def simple_hash(n, b):
    return int.from_bytes(hashlib.sha256(str(n).encode()).digest(), "little") % b


def create_arrow_data(n_rows):
    inner_count = int(n_rows / 25)
    rotates = []
    shears = []
    x = []
    y = []
    x_choices = ["a", "b", "c"]
    random.seed(0)
    for i, (rotate, shear, _) in enumerate(
        itertools.product(range(5), range(5), range(inner_count))
    ):
        rotates.append(rotate)
        shears.append(shear)
        x.append(x_choices[simple_hash(i**13, 3)])
        y.append(simple_hash(i, 10))
    table = pa.table(
        {
            "rotate": rotates,
            "shear": shears,
            "x": x,
            "y": y,
        }
    )
    table_list = ops.ArrowTableList(table)

    return storage.save(table_list)


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
    assert weave.use(node[0]).as_py() == 15
    assert weave.use(node[4]).as_py() == 17


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
    # node = (
    #     weave.get(ref)
    #     .groupby(lambda row: ops.dict_(rotate=row["rotate"]))[0]
    #     .pick("x")
    #     .groupby(lambda row: ops.dict_(row=row))
    #     # .map(lambda row: row.key.merge(ops.dict_(count=row.count()), _index: index}))
    # .map(lambda row: row.key().merge(ops.dict_(count=row.count())))
    #     .count()
    # )
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
    data = [
        {"a": 5, "im": Image.linear_gradient("L").rotate(0)},
        {"a": 6, "im": Image.linear_gradient("L").rotate(4)},
    ]
    ref = storage.save(data)
    storage.get(str(ref))
