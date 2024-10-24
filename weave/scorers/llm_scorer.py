from pydantic import Field, field_validator

from weave.scorers.base_scorer import Scorer
from weave.scorers.llm_utils import (
    _LLM_CLIENTS,
    _LLM_CLIENTS_NAMES,
    instructor_client,
)


class LLMScorer(Scorer):
    """Score a model output using an LLM"""

    client: _LLM_CLIENTS = Field(
        description="The LLM client to use, has to be instantiated with an api_key"
    )
    model_id: str = Field(description="The model to use")

    @field_validator("client")
    def validate_client(cls, v):  # type: ignore
        client_type_name = type(v).__name__
        if client_type_name not in _LLM_CLIENTS_NAMES:
            raise ValueError(
                f"Invalid client type. Expected one of {_LLM_CLIENTS_NAMES}, got {client_type_name}"
            )
        return v


class InstructorLLMScorer(Scorer):
    """Score a model output using an LLM"""

    client: _LLM_CLIENTS = Field(
        description="The LLM client to use, has to be instantiated with an api_key"
    )
    model_id: str = Field(description="The model to use")
    temperature: float = Field(
        ..., description="The temperature to use for the response"
    )
    max_tokens: int = Field(
        ..., description="The maximum number of tokens in the response"
    )

    @field_validator("client")
    def validate_client(cls, v):  # type: ignore
        client_type_name = type(v).__name__
        if client_type_name not in _LLM_CLIENTS_NAMES:
            raise ValueError(
                f"Invalid client type. Expected one of {_LLM_CLIENTS_NAMES}, got {client_type_name}"
            )
        return instructor_client(v)
