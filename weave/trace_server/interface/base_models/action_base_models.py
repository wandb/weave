from typing import Any, Literal, Optional, Union

from pydantic import BaseModel


class LlmJudgeActionSpec(BaseModel):
    action_type: Literal["llm_judge"] = "llm_judge"
    model: Literal["gpt-4o", "gpt-4o-mini"]
    prompt: str
    response_format: Optional[dict[str, Any]]


class ContainsWordsActionSpec(BaseModel):
    action_type: Literal["contains_words"] = "contains_words"
    target_words: list[str]


class WordCountActionSpec(BaseModel):
    action_type: Literal["wordcount"] = "wordcount"


class NoopActionSpec(BaseModel):
    action_type: Literal["noop"] = "noop"


ActionSpecType = Union[
    LlmJudgeActionSpec,
    ContainsWordsActionSpec,
    WordCountActionSpec,
    NoopActionSpec,
]


# TODO: Make this a baseObject
class Action(BaseModel):
    name: str
    spec: ActionSpecType


# CRITICAL! When saving this object, always set the object_id == "op_id-action_id"
# TODO: Make this a baseObject
class ActionDispatchFilter(BaseModel):
    op_name: str
    sample_rate: float
    action_ref: str
    disabled: Optional[bool] = False
