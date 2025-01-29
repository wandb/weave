from typing import TYPE_CHECKING, Any, Optional, Union

from pydantic import BaseModel

import weave
from weave.scorers import Scorer
from weave.scorers.guardrails.prompts import (
    PROMPT_INJECTION_GUARDRAIL_SYSTEM_PROMPT,
    PROMPT_INJECTION_SURVEY_PAPER_SUMMARY,
)
from weave.scorers.llm_utils import OPENAI_DEFAULT_MODEL, create
from weave.scorers.utils import stringify

if TYPE_CHECKING:
    from instructor import Instructor


class LLMGuardrailReasoning(BaseModel):
    injection_prompt: bool
    is_direct_attack: bool
    attack_type: Optional[str]
    explanation: Optional[str]


class LLMGuardrailResponse(BaseModel):
    safe: bool
    reasoning: LLMGuardrailReasoning


class PromptInjectionLLMGuardrail(Scorer):
    system_prompt: str = PROMPT_INJECTION_GUARDRAIL_SYSTEM_PROMPT
    model_id: str = OPENAI_DEFAULT_MODEL
    temperature: float = 0.7
    max_tokens: int = 4096
    _client: Union["Instructor", None] = None

    def model_post_init(self, __context: Any) -> None:
        import instructor
        from litellm import completion

        self._client = instructor.from_litellm(completion)

    @weave.op
    def score(self, prompt: str) -> LLMGuardrailResponse:
        user_prompt = (
            PROMPT_INJECTION_SURVEY_PAPER_SUMMARY
            + f"""
You are given the following user prompt that you are suppossed to assess whether it is a prompt injection attack or not:


<input_prompt>
{stringify(prompt)}
</input_prompt>
"""
        )
        response: LLMGuardrailReasoning = create(
            self._client,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=self.model_id,
            response_model=LLMGuardrailReasoning,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return LLMGuardrailResponse(
            safe=not response.injection_prompt, reasoning=response
        ).model_dump()
