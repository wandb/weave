from typing import Any, Literal, Optional, Union

from pydantic import BaseModel


class ConfiguredLlmJudgeAction(BaseModel):
    action_type: Literal["llm_judge"] = "llm_judge"
    model: Literal["gpt-4o", "gpt-4o-mini"]
    prompt: str
    response_format: Optional[dict[str, Any]]


class ConfiguredContainsWordsAction(BaseModel):
    action_type: Literal["contains_words"] = "contains_words"
    target_words: list[str]


class ConfiguredWordCountAction(BaseModel):
    action_type: Literal["wordcount"] = "wordcount"


class ConfiguredNoopAction(BaseModel):
    action_type: Literal["noop"] = "noop"



ActionConfigType = Union[
    ConfiguredLlmJudgeAction,
    ConfiguredContainsWordsAction,
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
