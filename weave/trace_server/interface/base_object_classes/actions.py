from typing import Any, Literal, Optional, Union

from pydantic import BaseModel

from weave.trace_server.interface.base_object_classes import base_object_def


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


# TODO: Make sure we really like this name - it is permanent
class ActionDefinition(base_object_def.BaseObject):
    name: str
    spec: ActionSpecType
