from pydantic import BaseModel, create_model
from . import weave_types as types
import typing
import enum


class JSONType(enum.Enum):
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NULL = "null"


class JSONSchema(typing.TypedDict, total=False):
    title: str
    type: JSONType
    properties: "typing.Optional[typing.Dict[str, JSONSchema]]"
    required: typing.Optional[typing.List[str]]
    items: "typing.Optional[typing.Union[JSONSchema, JSONType]]"  # Type of array items


def weave_type_to_pydantic(
    property_types: dict[str, types.Type], name: str
) -> BaseModel:
    field_types = {}
    for k, v in property_types.items():
        if isinstance(v, types.TypedDict):
            field_types[k] = weave_type_to_pydantic(v.property_types, "TypedDict")
        else:
            instance_classes = v._instance_classes()
            if not instance_classes:
                raise ValueError(f"Cannot convert {v} to pydantic")
            field_types[k] = instance_classes[0]  # type: ignore
    field_defs = {k: (v, ...) for k, v in field_types.items()}
    return create_model(name, **field_defs)  # type: ignore


def json_schema_to_weave_type(json_schema: JSONSchema) -> types.Type:
    type = JSONType(json_schema["type"])
    if type == JSONType.INTEGER:
        return types.Int()
    elif type == JSONType.NUMBER:
        return types.Number()
    elif type == JSONType.STRING:
        return types.String()
    elif type == JSONType.NULL:
        return types.NoneType()
    elif type == JSONType.BOOLEAN:
        return types.Boolean()
    elif type == JSONType.ARRAY:
        items_type = json_schema["items"]
        assert items_type is not None, "No items type given for array"
        if not isinstance(items_type, dict):
            items_type = {"type": items_type}
        return types.List(json_schema_to_weave_type(items_type))
    elif type == JSONType.OBJECT:

        properties = json_schema.get("properties", {}) or {}
        weave_properties = {
            key: json_schema_to_weave_type(value) for key, value in properties.items()
        }

        required_keys: set[str] = set(json_schema.get("required", []) or [])
        not_required = set(properties.keys()) - required_keys

        return types.TypedDict(weave_properties, not_required_keys=not_required)
    raise ValueError(f"Could not get weave type for json schema {json_schema}")
