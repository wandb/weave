from typing import Literal

from pydantic import BaseModel


class _BuiltinAction(BaseModel):
    action_type: Literal["builtin"] = "builtin"
    name: str


class ConfiguredAction(BaseModel):
    name: str
    action: _BuiltinAction
    config: dict


class ActionDispatchFilter(BaseModel):
    name: str
    sample_rate: float
    configured_action_ref: str
