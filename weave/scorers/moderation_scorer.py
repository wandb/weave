from typing import Any

from pydantic import field_validator

import weave
from weave.scorers.llm_scorer import LLMScorer
from weave.scorers.llm_utils import _LLM_CLIENTS, OPENAI_DEFAULT_MODERATION_MODEL


class OpenAIModerationScorer(LLMScorer):
    """Use OpenAI moderation API to check if the model output is safe.

    Args:
        model_id: The OpenAI model to use for moderation. Defaults to `text-moderation-latest`.
    """

    model_id: str = OPENAI_DEFAULT_MODERATION_MODEL

    @field_validator("client")
    def validate_openai_client(cls, v: _LLM_CLIENTS) -> _LLM_CLIENTS:
        # Method implementation
        try:
            from openai import (  # Ensure these are the correct imports
                AsyncOpenAI,
                OpenAI,
            )
        except ImportError:
            raise ValueError("Install openai to use this scorer")

        if not isinstance(v, (OpenAI, AsyncOpenAI)):
            raise TypeError("Moderation scoring only works with OpenAI or AsyncOpenAI")
        return v

    @weave.op
    def score(self, output: Any) -> dict:
        response = self.client.moderations.create(
            model=self.model_id,
            input=output,
        ).results[0]
        categories = {k: v for k, v in response.categories.to_dict().items() if v}
        return {"flagged": response.flagged, "categories": categories}
