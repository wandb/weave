import pyarrow as pa
from . import mappers_arrow
from . import weave_types as types


def test_map_list():
    d = [{"a": 5, "b": "x"}]
    d_type = types.TypeRegistry.type_of(d)
    m = mappers_arrow.map_to_arrow(d_type, None)
    res_type = m.result_type()
    assert res_type == pa.list_(
        pa.field(
            "x", pa.struct([pa.field("a", pa.int64()), pa.field("b", pa.string())])
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
        pa.field("x", pa.struct([pa.field("a", pa.int64()), pa.field("b", pa.null())]))
    )
    d2 = m.apply(d)
    assert d == d2
    m2 = mappers_arrow.map_from_arrow(d_type, None)
    d3 = m2.apply(d2)
    assert d2 == d3
