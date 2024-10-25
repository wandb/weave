from typing import Any, Literal, Optional, Union

from pydantic import BaseModel


class ConfiguredLlmJudgeAction(BaseModel):
    action_type: Literal["llm_judge"]
    prompt: str
    response_format: Optional[dict[str, Any]]


class ConfiguredWordCountAction(BaseModel):
    action_type: Literal["wordcount"]


class ConfiguredNoopAction(BaseModel):
    action_type: Literal["noop"]


ActionConfigType = Union[
    ConfiguredLlmJudgeAction,
    ConfiguredWordCountAction,
    ConfiguredNoopAction,
]


class ConfiguredAction(BaseModel):
    name: str
    config: ActionConfigType


# CRITICAL! When saving this object, always set the object_id == "op_id-action_id"
class ActionDispatchFilter(BaseModel):
    op_name: str
    sample_rate: float
    configured_action_ref: str
    disabled: Optional[bool] = None
