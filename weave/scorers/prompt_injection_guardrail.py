import warnings
from typing import Any, Optional

from pydantic import BaseModel, Field

import weave
from weave.flow.scorer import WeaveScorerResult
from weave.scorers.default_models import OPENAI_DEFAULT_MODEL
from weave.scorers.prompts import (
    PROMPT_INJECTION_GUARDRAIL_SYSTEM_PROMPT,
    PROMPT_INJECTION_GUARDRAIL_USER_PROMPT,
    PROMPT_INJECTION_SURVEY_PAPER_SUMMARY,
)
from weave.scorers.scorer_types import LLMScorer


class LLMGuardrailReasoning(BaseModel):
    injection_prompt: bool
    is_direct_attack: bool
    attack_type: Optional[str]
    explanation: Optional[str]


SUPPORTED_MODELS = ["gpt-4o", "gpt-4o-mini", "o1-preview", "o1-mini", "o1", "o3-mini"]


class PromptInjectionLLMGuardrail(LLMScorer):
    """
    The `PromptInjectionLLMGuardrail` uses an LLM to assess whether a prompt
    is a prompt injection attack or not. It uses a prompting strategy that is based on
    a summarized version of the research paper
    [An Early Categorization of Prompt Injection Attacks on Large Language Models](https://arxiv.org/abs/2402.00898)
    that contains the taxonomy of prompt injection attacks and the criteria and definitions for each attack type.

    Attributes:
        system_prompt (str): The prompt describing the task of detecting prompt injection attacks.
        model_id (str): The LLM model name, depends on the LLM's providers to be used `client` being used.
        temperature (float): LLM temperature setting.
        max_tokens (int): Maximum number of tokens in the LLM's response.
    """

    system_prompt: str = PROMPT_INJECTION_GUARDRAIL_SYSTEM_PROMPT
    model_id: str = OPENAI_DEFAULT_MODEL
    temperature: float = Field(
        default=0.7,
        description="Controls randomness in the LLM's responses (0.0 to 1.0)",
    )
    max_tokens: int = Field(
        default=4096,
        description="Maximum number of tokens allowed in the LLM's response",
    )

    def model_post_init(self, __context: Any) -> None:
        if self.model_id not in SUPPORTED_MODELS:
            warnings.warn(
                f"The prompting strategy used in this guardrail has been tested with the following models: {', '.join(SUPPORTED_MODELS)}."
                f"The model {self.model_id} might not yield the best results for this guardrail."
            )

    @weave.op
    async def score(self, *, output: str, **kwargs: Any) -> WeaveScorerResult:
        user_prompt = PROMPT_INJECTION_GUARDRAIL_USER_PROMPT.format(
            research_paper_summary=PROMPT_INJECTION_SURVEY_PAPER_SUMMARY,
            prompt=output,
        )
        response = await self._acompletion(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=self.model_id,
            response_format=LLMGuardrailReasoning,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        response = LLMGuardrailReasoning.model_validate_json(
            response.choices[0].message.content
        )
        return WeaveScorerResult(
            passed=not response.injection_prompt,
            metadata={"reason": response.explanation},
        )
