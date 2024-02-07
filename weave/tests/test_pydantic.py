from typing import Optional
import pydantic

import weave
from weave import weave_types as types
from weave.weave_pydantic import json_schema_to_weave_type


def test_jsonschema_to_weave_type():

    assert json_schema_to_weave_type({"type": "integer"}) == types.Int()
    assert json_schema_to_weave_type(
        {"type": "array", "items": {"type": "integer"}}
    ) == types.List(types.Int())

    assert json_schema_to_weave_type(
        {
            "type": "object",
            "properties": {"a": {"type": "integer"}},
            "required": ["a"],
        }
    ) == types.TypedDict({"a": types.Int()})

    assert json_schema_to_weave_type({"type": "null"}) == types.NoneType()

    assert json_schema_to_weave_type(
        {
            "type": "object",
            "properties": {
                "a": {
                    "type": "integer",
                },
                "b": {"type": "object", "properties": {"b": {"type": "string"}}},
            },
            "required": ["a"],
        }
    ) == types.TypedDict(
        {
            "a": types.Int(),
            "b": types.TypedDict({"b": types.String()}, not_required_keys={"b"}),
        },
        not_required_keys={"b"},
    )


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
        "c": types.Number(),
    }


def test_save_load_pydantic():
    class TestPydanticClass(pydantic.BaseModel):
        a: int

    obj = TestPydanticClass(a=1)
    n = weave.save(obj)
    recovered = weave.use(n)
    assert recovered.a == 1


def test_pydantic_saveload():
    class Object(pydantic.BaseModel):
        name: Optional[str] = "hello"
        description: Optional[str] = None

    class A(Object):
        model_name: str

    class B(A):
        pass

    a = B(name="my-a", model_name="my-model")

    a_type = weave.type_of(a)
    assert a_type.root_type_class().__name__ == "A"

    weave.init_local_client()
    weave.publish(a, name="my-a")

    a2 = weave.ref("my-a").get()
    assert a2.name == "my-a"
    assert a2.description == None
    assert a2.model_name == "my-model"
