from pydantic import Field, field_validator

import weave
from weave.scorers.llm_utils import (
    _LLM_CLIENTS,
    _LLM_CLIENTS_NAMES,
    instructor_client,
)


class LLMScorer(weave.Scorer):
    """Score model outputs using a Large Language Model (LLM).

    This scorer leverages LLMs to evaluate and score model outputs. It provides a flexible
    way to use different LLM providers for scoring purposes.

    Attributes:
        client: An instantiated LLM client with valid API credentials
        model_id: The specific model identifier to use for scoring
    """

    client: _LLM_CLIENTS = Field(
        description="The LLM client to use, has to be instantiated with an api_key"
    )
    model_id: str = Field(description="The model to use")

    @field_validator("client")
    def validate_client(cls, v: _LLM_CLIENTS) -> _LLM_CLIENTS:
        client_type_name = type(v).__name__
        if client_type_name not in _LLM_CLIENTS_NAMES:
            raise ValueError(
                f"Invalid client type. Expected one of {_LLM_CLIENTS_NAMES}, got {client_type_name}"
            )
        return v


class InstructorLLMScorer(weave.Scorer):
    """Score a model using an LLM with structured outputs.

    This scorer extends the base LLM scoring capability by adding temperature and
    token control for more precise scoring behavior. It automatically wraps the
    provided client with [instructor](https://github.com/instructor-ai/instructor)
    functionality for structured outputs.

    Attributes:
        client: An instantiated LLM client with valid API credentials
        model_id: The specific model identifier to use for scoring
        temperature: Controls randomness in the LLM's responses (0.0 to 1.0)
        max_tokens: Maximum number of tokens allowed in the LLM's response
    """

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
    def validate_client(cls, v: _LLM_CLIENTS) -> _LLM_CLIENTS:
        client_type_name = type(v).__name__
        if client_type_name not in _LLM_CLIENTS_NAMES:
            raise ValueError(
                f"Invalid client type. Expected one of {_LLM_CLIENTS_NAMES}, got {client_type_name}"
            )
        return instructor_client(v)
