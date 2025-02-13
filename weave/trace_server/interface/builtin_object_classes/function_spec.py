from weave.trace_server.interface.builtin_object_classes import base_object_def
from pydantic import BaseModel, Field, create_model, field_validator, model_validator
from typing import Any


class FunctionSpec(base_object_def.BaseObject):
    name: str = Field(default="", description="The name of the function")
    description: str = Field(default="", description="A description of the function")
    parameters: dict[str, Any] = Field(
        default={}, description="The parameters of the function"
    )
    returns: dict[str, Any] = Field(
        default={}, description="The return value of the function"
    )
