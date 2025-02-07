from typing import Any, Optional

from litellm import acompletion
from pydantic import BaseModel

import weave
from weave.scorers.default_models import OPENAI_DEFAULT_MODEL
from weave.scorers.guardrails.prompts import (
    PROMPT_INJECTION_GUARDRAIL_SYSTEM_PROMPT,
    PROMPT_INJECTION_GUARDRAIL_USER_PROMPT,
    PROMPT_INJECTION_SURVEY_PAPER_SUMMARY,
)
from weave.scorers.llm_scorer import LLMScorer
from weave.scorers.utils import stringify


class LLMGuardrailReasoning(BaseModel):
    injection_prompt: bool
    is_direct_attack: bool
    attack_type: Optional[str]
    explanation: Optional[str]


class LLMGuardrailResponse(BaseModel):
    flagged: bool
    reason: LLMGuardrailReasoning


class PromptInjectionLLMGuardrail(LLMScorer):
    """
    The `PromptInjectionLLMGuardrail` uses an LLM to assess whether a prompt
    is a prompt injection attack or not.

    Attributes:
        system_prompt (str): The prompt describing the task of detecting prompt injection attacks.
            The system prompt is a summarized version of the research paper
            [An Early Categorization of Prompt Injection Attacks on Large Language Models](https://arxiv.org/abs/2402.00898)
            that contains the taxonomy of prompt injection attacks and the criteria and definitions for each attack type.
        model_id (str): The LLM model name, depends on the LLM's providers to be used `client` being used.
        temperature (float): LLM temperature setting.
        max_tokens (int): Maximum number of tokens in the LLM's response.
    """

    system_prompt: str = PROMPT_INJECTION_GUARDRAIL_SYSTEM_PROMPT
    model_id: str = OPENAI_DEFAULT_MODEL
    temperature: float = 0.7
    max_tokens: int = 4096

    @weave.op
    async def score(self, output: str) -> dict[str, Any]:
        user_prompt = PROMPT_INJECTION_GUARDRAIL_USER_PROMPT.format(
            research_paper_summary=PROMPT_INJECTION_SURVEY_PAPER_SUMMARY,
            prompt=stringify(output),
        )
        response = await acompletion(
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
        return LLMGuardrailResponse(
            flagged=response.injection_prompt, reason=response
        ).model_dump()
