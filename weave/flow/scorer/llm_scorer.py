import json
from typing import Any, Type

import numpy as np
from pydantic import BaseModel, Field, field_validator

from weave.flow.scorer.base_scorer import Scorer
from weave.flow.scorer.llm_utils import embed, instructor_client, OPENAI_DEFAULT_MODEL, _LLM_CLIENT_TYPES

try:
    from openai import AsyncOpenAI, OpenAI
except:
    pass
class LLMScorer(Scorer):
    """Score a model output using an LLM"""

    client: Any = Field(
        description="The LLM client to use, has to be instantiated with an api_key"
    )
    model_id: str = Field(description="The model to use")

    @field_validator("client")
    def validate_client(cls, v):
        if not any(isinstance(v, client_type) for client_type in _LLM_CLIENT_TYPES):
            raise ValueError(
                f"Invalid client type. Expected one of {_LLM_CLIENT_TYPES}, got {type(v)}"
            )
        return v

class InstructorLLMScorer(Scorer):
    """Score a model output using an LLM"""

    client: Any = Field(
        description="The LLM client to use, has to be instantiated with an api_key"
    )
    model_id: str = Field(description="The model to use")
    temperature: float = Field(..., description="The temperature to use for the response")
    max_tokens: int = Field(..., description="The maximum number of tokens in the response")

    @field_validator("client")
    def validate_client(cls, v):
        if not any(isinstance(v, client_type) for client_type in _LLM_CLIENT_TYPES):
            raise ValueError(
                f"Invalid client type. Expected one of {_LLM_CLIENT_TYPES}, got {type(v)}"
            )
        return instructor_client(v)