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
