from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

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


class ActionDefinition(base_object_def.BaseObject):
    spec: ActionSpecType = Field(..., discriminator="action_type")

    # This is needed because the name field is optional in the base class, but required
    # in the derived class. Pyright doesn't like having a stricter type
    # `Variable is mutable so its type is invariant`: Override type "str" is not the same as base type "str | None".
    # Therefore, we just validate the name as a post-init method.
    @field_validator("name")
    def name_must_be_set(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            raise ValueError("name must be set")
        return v