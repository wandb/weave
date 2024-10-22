from typing import Literal

from pydantic import BaseModel


class JSONSchema(BaseModel):
    schema: dict


# This is only here for completeness, I think we are going to hardcode a list for now so they don't need to exist in every project
class BuiltinAction(BaseModel):
    action_type: Literal["builtin"] = "builtin"
    name: str
    digest: str = "*"
    # input_schema: JSONSchema
    # config_schema: JSONSchema


class ActionWithConfig(BaseModel):
    name: str
    action: BuiltinAction
    config: dict


# # Future
# class OpAction(Action):
#     action_type: Literal["op"]
#     op: Op


class ActionOpMapping(BaseModel):
    action: ActionWithConfig
    op_name: str
    op_digest: str
    input_mapping: dict[str, str]  # Input field name -> Call selector


class ActionFilterTrigger(BaseModel):
    attribute_filter: dict[str, str]  # Could the CallFilter.
    sample_rate: float
    mapping: ActionOpMapping
    config: dict
