from typing import Any, Optional

import jsonschema
from pydantic import BaseModel, Field, create_model, field_validator, model_validator
from pydantic.fields import FieldInfo

from weave.trace_server.interface.builtin_object_classes import base_object_def

SUPPORTED_PRIMITIVES = (int, float, bool, str)


class AnnotationSpec(base_object_def.BaseObject):
    field_schema: dict[str, Any] = Field(
        default={},
        description="Expected to be valid JSON Schema. Can be provided as a dict, a Pydantic model class, a tuple of a primitive type and a Pydantic Field, or primitive type",
        examples=[
            # String feedback
            {"type": "string", "maxLength": 100},
            # Number feedback
            {"type": "number", "minimum": 0, "maximum": 100},
            # Integer feedback
            {"type": "integer", "minimum": 0, "maximum": 100},
            # Boolean feedback
            {"type": "boolean"},
            # Categorical feedback
            {"type": "string", "enum": ["option1", "option2"]},
        ],
    )

    # TODO
    # If true, all unique creators will have their
    # own value for this feedback type. Otherwise,
    # by default, the value is shared and can be edited.
    unique_among_creators: bool = False

    # TODO
    # If provided, this feedback type will only be shown
    # when a call is generated from the given op ref
    op_scope: Optional[list[str]] = Field(
        default=None,
        examples=[
            ["weave:///entity/project/op/name:digest"],
            ["weave:///entity/project/op/name:*"],
        ],
    )

    @model_validator(mode="before")
    @classmethod
    def preprocess_field_schema(cls, data: dict[str, Any]) -> dict[str, Any]:
        if "field_schema" not in data:
            return data

        field_schema = data["field_schema"]

        temp_field_tuple = None
        # Handle Pydantic Field
        if isinstance(field_schema, tuple):
            if len(field_schema) != 2:
                raise ValueError("Expected a tuple of length 2")
            annotation, field = field_schema
            if (
                not isinstance(annotation, type)
            ) or annotation not in SUPPORTED_PRIMITIVES:
                raise TypeError("Expected annotation to be a primitive type")
            if not isinstance(field, FieldInfo):
                raise TypeError("Expected field to be a Pydantic Field")
            temp_field_tuple = (annotation, field)
        elif field_schema in SUPPORTED_PRIMITIVES:
            temp_field_tuple = (field_schema, Field())

        if temp_field_tuple is not None:
            # Create a temporary model to leverage Pydantic's schema generation
            TempModel = create_model("TempModel", field=temp_field_tuple)

            schema = TempModel.model_json_schema()["properties"]["field"]

            if (
                "title" in schema and schema["title"] == "Field"
            ):  # default title for Field
                schema.pop("title")

            data["field_schema"] = schema
            return data

        # Handle Pydantic model
        if isinstance(field_schema, type) and issubclass(field_schema, BaseModel):
            data["field_schema"] = field_schema.model_json_schema()  # type: ignore
            return data

        return data

    @field_validator("field_schema")
    def validate_field_schema(cls, schema: dict[str, Any]) -> dict[str, Any]:
        # Validate the schema
        try:
            jsonschema.validate(None, schema)
        except jsonschema.exceptions.SchemaError as e:
            raise e
        except jsonschema.exceptions.ValidationError:
            pass  # we don't care that `None` does not conform
        return schema

    def value_is_valid(self, payload: Any) -> bool:
        """
        Validates a payload against this annotation spec's schema.

        Args:
            payload: The data to validate against the schema

        Returns:
            bool: True if validation succeeds, False otherwise
        """
        try:
            jsonschema.validate(payload, self.field_schema)
        except jsonschema.exceptions.ValidationError:
            return False
        return True
