from typing import Optional

import jsonschema
from pydantic import Field, field_validator

from weave.trace_server.interface.base_object_classes import base_object_def


class AnnotationSpec(base_object_def.BaseObject):
    json_schema: dict = Field(
        default={},
        description="Expected to be valid JSON Schema",
        examples=[
            # String feedback
            {"type": "string", "max_length": 100},
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

    @field_validator("json_schema")
    def validate_json_schema(cls, v: dict) -> dict:
        try:
            jsonschema.validate(None, v)
        except jsonschema.exceptions.SchemaError as e:
            raise e
        except jsonschema.exceptions.ValidationError:
            pass  # we don't care that `None` does not conform
        return v
