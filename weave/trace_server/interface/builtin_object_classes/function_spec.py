from weave.trace_server.interface.builtin_object_classes import base_object_def
from pydantic import BaseModel, Field, create_model, field_validator, model_validator
from typing import Any, Optional, TypedDict

class FunctionParameter(TypedDict, total=False):
    name: str
    description: str
    type: str
    items: Optional[dict[str, Any]] = None


class FunctionParameters(TypedDict):
    type: str
    properties: dict[str, FunctionParameter]
    required: list[str]

class FunctionSpec(base_object_def.BaseObject):
    name: str = Field(default="", description="The name of the function")
    description: str = Field(default="", description="A description of the function")
    parameters: FunctionParameters = Field(default=FunctionParameters(), description="The parameters of the function")


"""
Example:
{
  "name": "getData",
  "description": "Select data based on names and dates",
  "parameters": {
    "type": "object",
    "properties": {
      "names": {
        "description": "List of names",
        "type": "array",
        "name": "names",
        "items": {
          "type": "string"
        }
      },
      "start_date": {
        "description": "Start date for historical data (YYYY-MM-DD)",
        "type": "string",
        "name": "start_date"
      },
      "end_date": {
        "description": "End date for historical data (YYYY-MM-DD)",
        "type": "string",
        "name": "end_date"
      }
    },
    "required": [
      "names",
      "start_date",
      "end_date"
    ]
  }
}
"""