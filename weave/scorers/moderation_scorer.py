from typing import Any

from litellm import amoderation

import weave
from weave.scorers.default_models import OPENAI_DEFAULT_MODERATION_MODEL


class OpenAIModerationScorer(weave.Scorer):
    """
    Uses the OpenAI moderation API to check if the model output is safe.

    This scorer sends the provided output to the OpenAI moderation API and returns a structured response
    indicating whether the output contains unsafe content.

    Attributes:
        model_id (str): The OpenAI moderation model identifier to be used. Defaults to `OPENAI_DEFAULT_MODERATION_MODEL`.
    """

    model_id: str = OPENAI_DEFAULT_MODERATION_MODEL

    @weave.op
    async def score(self, output: Any) -> dict:
        response = await amoderation(
            model=self.model_id,
            input=output,
        )
        response = response.results[0]
        categories = {k: v for k, v in response.categories.model_dump().items() if v}
        return {"flagged": response.flagged, "categories": categories}
