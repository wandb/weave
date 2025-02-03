from typing import Any, TypedDict

from litellm import amoderation

import weave
from weave.scorers.base_scorer import Scorer
from weave.scorers.llm_utils import OPENAI_DEFAULT_MODERATION_MODEL


class OpenAIModerationScorerOutput(TypedDict):
    """Output type for OpenAIModerationScorer."""

    flagged: bool
    categories: dict[str, bool]


class OpenAIModerationScorer(Scorer):
    """Use OpenAI moderation API to check if the model output is safe.

    Args:
        model_id: The OpenAI model to use for moderation. Defaults to `text-moderation-latest`.
    """

    model_id: str = OPENAI_DEFAULT_MODERATION_MODEL

    @weave.op
    async def score(self, output: Any) -> OpenAIModerationScorerOutput:
        response = await amoderation(
            model=self.model_id,
            input=output,
        )
        response = response.results[0]
        categories = {k: v for k, v in response.categories.model_dump().items() if v}
        return {"flagged": response.flagged, "categories": categories}
