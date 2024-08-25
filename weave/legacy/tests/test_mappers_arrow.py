import math

import pyarrow as pa

from weave.legacy.weave import mappers_arrow
from weave.legacy.weave import weave_types as types


def test_map_list():
    d = [{"a": 5, "b": "x"}]
    d_type = types.TypeRegistry.type_of(d)
    m = mappers_arrow.map_to_arrow(d_type, None)
    res_type = m.result_type()
    assert res_type == pa.list_(
        pa.field(
            "item", pa.struct([pa.field("a", pa.int64()), pa.field("b", pa.string())])
        )
    )
    d2 = m.apply(d)
    assert d == d2
    m2 = mappers_arrow.map_from_arrow(d_type, None)
    d3 = m2.apply(d2)
    assert d2 == d3


def test_map_list_with_none():
    d = [{"a": 5, "b": None}]
    d_type = types.TypeRegistry.type_of(d)
    m = mappers_arrow.map_to_arrow(d_type, None)
    res_type = m.result_type()
    assert res_type == pa.list_(
        pa.field(
            "item", pa.struct([pa.field("a", pa.int64()), pa.field("b", pa.null())])
        )
    )
    d2 = m.apply(d)
    assert d == d2
    m2 = mappers_arrow.map_from_arrow(d_type, None)
    d3 = m2.apply(d2)
    assert d2 == d3


def test_map_list_with_maybe():
    d = [{"a": 6, "b": "x"}, {"a": 5, "b": None}]
    d_type = types.TypeRegistry.type_of(d)
    m = mappers_arrow.map_to_arrow(d_type, None)
    res_type = m.result_type()
    assert res_type == pa.list_(
        pa.field(
            "item", pa.struct([pa.field("a", pa.int64()), pa.field("b", pa.string())])
        )
    )
    d2 = m.apply(d)
    assert d == d2
    m2 = mappers_arrow.map_from_arrow(d_type, None)
    d3 = m2.apply(d2)
    assert d2 == d3


def test_map_list_with_nan():
    d = [{"a": 5, "b": float("nan")}]
    d_type = types.TypeRegistry.type_of(d)
    m = mappers_arrow.map_to_arrow(d_type, None)
    res_type = m.result_type()
    assert res_type == pa.list_(
        pa.field(
            "item", pa.struct([pa.field("a", pa.int64()), pa.field("b", pa.float64())])
        )
    )
    d2 = m.apply(d)
    assert d[0]["a"] == d2[0]["a"]
    assert math.isnan(d2[0]["b"])
    m2 = mappers_arrow.map_from_arrow(d_type, None)
    d3 = m2.apply(d2)
    assert d2[0]["a"] == d3[0]["a"]
    assert math.isnan(d3[0]["b"])


def test_mapper_list_to_arrow_arr_has_no_type():
    obj = [
        {
            "IDs": [264, 268, 29, 77, 47, 297, 73, 18, 366, 364],
            "Transformations": "a",
        },
        {
            "IDs": None,
            "Transformations": "b",
        },
    ]
    ot = types.TypeRegistry.type_of(obj)

    # this should not raise an exception
    m = mappers_arrow.map_to_arrow(ot, None)
    m2 = mappers_arrow.map_from_arrow(ot, None)
    transformed = m.apply(obj)
    untransformed = m2.apply(transformed)

    # this should work with nulls
    assert untransformed == obj
