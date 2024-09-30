from typing import Any, Optional

import pydantic

import weave_query as weave
import weave_query
from weave_query import weave_types as types


def test_pydantic_type_inference():
    class TestPydanticClass(pydantic.BaseModel):
        a: int
        b: str
        c: float

    obj = TestPydanticClass(a=1, b="2", c=3.0)
    t = types.TypeRegistry.type_of(obj)
    assert isinstance(t, types.ObjectType)
    assert t.property_types() == {
        "a": types.Int(),
        "b": types.String(),
        "c": types.Float(),
    }


def test_save_load_pydantic():
    class TestPydanticClass(pydantic.BaseModel):
        a: int

    obj = TestPydanticClass(a=1)
    n = weave.save(obj)
    recovered = weave.use(n)
    assert recovered.a == 1


def test_pydantic_nested_type():
    class Child(pydantic.BaseModel):
        a: str

    class Parent(pydantic.BaseModel):
        child: Child
        b: int

    p = Parent(child=Child(a="hello"), b=1)
    t = weave.type_of(p)

    assert str(t) == "Parent(child=Child(a=String()), b=Int())"
    assert t.to_dict() == {
        "type": "Parent",
        "_base_type": {"type": "Object"},
        "_relocatable": True,
        "_is_object": True,
        "child": {
            "type": "Child",
            "_base_type": {"type": "Object"},
            "_relocatable": True,
            "_is_object": True,
            "a": "string",
        },
        "b": "int",
    }
