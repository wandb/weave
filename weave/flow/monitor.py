from pydantic import Field, field_validator

from weave.flow.obj import Object
from weave.flow.casting import ScorerLike
from weave.trace.objectify import register_object

"""
_MONGO_FILTER_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "call_filter",
    "type": "object",
    "$defs": {
        "literal": {
            "type": ["number", "string", "boolean", "null"],
            "description": "A literal value"
        },
        "binary_operator": {
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "$getField": {"type": "string"},
                    "$literal": {"$ref": "#/$defs/literal"}
                }
            }
        }
    },
    "properties": {
        "op_names": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },
        "query": {
            "type": "object",
            "properties": {
                "$expr": {
                    "type": "object",
                    "properties": {
                        "$gt": {"$ref": "#/$defs/binary_operator"},
                        "$ge": {"$ref": "#/$defs/binary_operator"},
                        "$lt": {"$ref": "#/$defs/binary_operator"},
                        "$le": {"$ref": "#/$defs/binary_operator"},
                        "$eq": {"$ref": "#/$defs/binary_operator"},
                        "$ne": {"$ref": "#/$defs/binary_operator"},
                    }
                }
            }
        }
    }
}
"""


@register_object
class Monitor(Object):
    """
    Sets up a monitor to score incoming calls automatically.
    """
    sampling_rate: float = Field(ge=0, le=1)
    scorers: list[ScorerLike]
    call_filter: dict 

    @field_validator("call_filter")
    @classmethod
    def _validate_call_filter(cls, call_filter: dict) -> dict:
        """
        Example filter:
        {
            "op_names": [
                "weave:///wandb/directeur-sportif/op/query_model:*"
            ],
            "query":{
                "$expr": {
                    "$gt": [
                        {
                            "$getField": "started_at"
                        },
                        {
                            "$literal": 1742540400
                        }
                    ]
                }
            }
        }
        """
        if not isinstance(call_filter, dict):
            raise ValueError("call_filter must be a dictionary")

        if "op_names" not in call_filter:
            raise ValueError("call_filter must contain an op_names key")

        if not isinstance(call_filter["op_names"], list):
            raise ValueError("op_names must be a list")

        if "query" not in call_filter:
            raise ValueError("call_filter must contain a query key")
        
        return call_filter