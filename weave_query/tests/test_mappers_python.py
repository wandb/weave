import math

from weave.legacy.weave import api, context, mappers_python, val_const, weave_internal
from weave.legacy.weave import weave_types as types


def test_map_typed_dict():
    d = {"a": 5, "b": "x"}
    d_type = types.TypeRegistry.type_of(d)
    m = mappers_python.map_to_python(d_type, None)
    # TODO: This fails because we start with ConstString and end up with String
    # assert d_type == d2_type
    d2 = m.apply(d)
    assert d == d2
    m2 = mappers_python.map_from_python(d_type, None)
    d3 = m2.apply(d2)
    assert d2 == d3


def test_map_dict():
    d = {"a": 5, "b": 9}
    d_type = types.Dict(types.String(), types.Int())
    m = mappers_python.map_to_python(d_type, None)
    d2 = m.apply(d)
    assert d == d2
    m2 = mappers_python.map_from_python(d_type, None)
    d3 = m2.apply(d2)
    assert d2 == d3


def test_map_type():
    t = types.TypedDict({"a": types.Int(), "b": types.String()})
    t_type = types.TypeRegistry.type_of(t)
    m = mappers_python.map_to_python(t_type, None)
    t2 = m.apply(t)
    m2 = mappers_python.map_from_python(t_type, None)
    t3 = m2.apply(t2)
    assert t == t3


def test_map_typed_dict_with_nan():
    d = {"a": 5, "b": float("nan")}
    d_type = types.TypeRegistry.type_of(d)
    m = mappers_python.map_to_python(d_type, None)
    d2 = m.apply(d)
    m2 = mappers_python.map_from_python(d_type, None)
    d3 = m2.apply(d2)
    assert d["a"] == d3["a"]
    assert math.isnan(d3["b"])


def test_map_const():
    d = {"a": val_const.const(5)}
    d_type = types.TypeRegistry.type_of(d)
    m = mappers_python.map_to_python(d_type, None)
    d2 = m.apply(d)
    m2 = mappers_python.map_from_python(d_type, None)
    d3 = m2.apply(d2)
    # const is the only case where the mapping is not two-way.
    # TODO: is this a problem?
    assert d3["a"] == 5


def test_map_union_none_type():
    d = None
    d_type = types.UnionType(types.TypeType(), types.NoneType())
    m = mappers_python.map_to_python(d_type, None)
    d2 = m.apply(d)
    m2 = mappers_python.map_from_python(d_type, None)
    d3 = m2.apply(d2)
    assert d3 is None
