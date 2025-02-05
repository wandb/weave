from pydantic import Field

import weave


class LLMScorer(weave.Scorer):
    """Score model outputs using a Large Language Model (LLM).

    This scorer leverages LLMs to evaluate and score model outputs. It provides a flexible
    way to use different LLM providers for scoring purposes.

    We are using litellm to support multiple LLM providers.

    Attributes:
        model_id: The specific model identifier to use for scoring
        temperature: Controls randomness in the LLM's responses (0.0 to 1.0)
        max_tokens: Maximum number of tokens allowed in the LLM's response
    """

    model_id: str = Field(
        description="The model to use, check https://docs.litellm.ai/docs/providers for supported models"
    )
    temperature: float = Field(
        ..., description="The temperature to use for the response"
    )
    max_tokens: int = Field(
        ..., description="The maximum number of tokens in the response"
    )

    # TODO: check if we can validate the model_id with litellm on a post_init method


class InstructorLLMScorer(LLMScorer):
    def __new__(cls, *args, **kwargs):
        raise DeprecationWarning(
            "InstructorLLMScorer is deprecated and will be removed in a future version. "
            "Use LLMScorer directly instead, which now has built-in support for structured outputs."
        )
