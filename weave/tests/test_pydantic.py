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
    assert t == types.ObjectType(a=types.Int(), b=types.String(), c=types.Number())


def test_save_load_pydantic():
    class TestPydanticClass(pydantic.BaseModel):
        a: int

    obj = TestPydanticClass(a=1)
    n = weave.save(obj)
    recovered = weave.use(n)
    assert recovered.a == 1
