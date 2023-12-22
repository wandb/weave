from weave import weave_types as types
from weave.weave_pydantic import json_schema_to_weave_type


def test_jsonschema_to_weave_type():

    assert json_schema_to_weave_type({"type": "integer"}) == types.Int()
    assert json_schema_to_weave_type(
        {"type": "array", "items": {"type": "integer"}}
    ) == types.List(types.Int())
