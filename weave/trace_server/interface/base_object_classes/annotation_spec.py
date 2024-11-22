from typing import Optional, Union, Type, Dict, Any

import jsonschema
from pydantic import BaseModel, field_validator, Field
from pydantic.fields import FieldInfo

from weave.trace_server.interface.base_object_classes import base_object_def


class AnnotationSpec(base_object_def.BaseObject):
    field_schema: Dict[str, Any] = Field(
        default={},
        description="Expected to be valid JSON Schema. Can be provided as a dict, a Pydantic model class, or a Pydantic Field",
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

    @field_validator("field_schema")
    def validate_field_schema(cls, v: Union[Dict[str, Any], Type[BaseModel], FieldInfo]) -> Dict[str, Any]:
        # Handle Pydantic Field
        if isinstance(v, FieldInfo):
            return v.json_schema()
        
        # Handle Pydantic model
        if isinstance(v, type) and issubclass(v, BaseModel):
            return v.model_json_schema()
            
        # Handle direct schema dict
        schema = v
            
        # Validate the schema
        try:
            jsonschema.validate(None, schema)
        except jsonschema.exceptions.SchemaError as e:
            raise e
        except jsonschema.exceptions.ValidationError:
            pass  # we don't care that `None` does not conform
        return schema

    def validate(self, payload: Any) -> bool:
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