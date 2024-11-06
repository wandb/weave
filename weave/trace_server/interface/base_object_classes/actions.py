from typing import Any, Literal, Union

from pydantic import BaseModel

from weave.trace_server.interface.base_object_classes import base_object_def


class LlmJudgeActionSpec(BaseModel):
    action_type: Literal["llm_judge"] = "llm_judge"
    # TODO: Remove this restriction (probably after initial release. We need to cross
    # reference which LiteLLM models support structured outputs)
    model: Literal["gpt-4o", "gpt-4o-mini"]
    prompt: str
    # Expected to be valid JSON Schema
    response_schema: dict[str, Any]


class ContainsWordsActionSpec(BaseModel):
    action_type: Literal["contains_words"] = "contains_words"
    target_words: list[str]


ActionSpecType = Union[
    LlmJudgeActionSpec,
    ContainsWordsActionSpec,
]


# TODO: Make sure we really like this name - it is permanent
class ActionDefinition(base_object_def.BaseObject):
    # Pyright doesn't like this override
    # name: str
    spec: ActionSpecType
