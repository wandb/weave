from typing import Any

from pydantic import BaseModel, Field

import weave
from weave import Scorer
from weave.scorers.default_models import OPENAI_DEFAULT_MODEL
from weave.scorers.guardrails.prompts import (
    PRIVILEGE_ESCALATION_SYSTEM_PROMPT,
    PRIVILEGE_ESCALATION_USER_PROMPT,
)
from weave.scorers.utils import stringify


class PrivilegeEscalationGuardrailResponse(BaseModel):
    flagged: bool = Field(
        description="Whether the prompt is a privilege escalation prompt or not. True if it is, False otherwise.",
    )
    reason: str = Field(
        description="Reasoning for why the prompt is a privilege escalation prompt or not.",
    )


class PrivilegeEscalationLLMGuardrail(Scorer):
    """
    The `PrivilegeEscalationLLMGuardrail` is used to detect privilege escalation attacks using an LLM.

    Attributes:
        system_prompt (str): The prompt describing the task of detecting privilege escalation attacks.
        model_id (str): The LLM model name, depends on the LLM's providers to be used `client` being used.
        temperature (float): LLM temperature setting.
        max_tokens (int): Maximum number of tokens in the LLM's response.
    """

    system_prompt: str = PRIVILEGE_ESCALATION_SYSTEM_PROMPT
    model_id: str = OPENAI_DEFAULT_MODEL
    temperature: float = 0.0
    max_tokens: int = 1024

    def model_post_init(self, __context: Any) -> None:
        if self.model_id not in [
            "gpt-4o",
            "gpt-4o-mini",
            "o1-preview",
            "o1-mini",
            "o1",
        ]:
            raise ValueError(
                "The system prompt for this guardrail was tested with OpenAI models. \
                If you're using a different model, you may need to adjust the system prompt."
            )

    @weave.op
    async def score(self, output: str) -> PrivilegeEscalationGuardrailResponse:
        from litellm import acompletion

        output = stringify(output)
        response = (
            acompletion(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {
                        "role": "user",
                        "content": PRIVILEGE_ESCALATION_USER_PROMPT.format(
                            prompt=output
                        ),
                    },
                ],
                model=self.model_id,
                response_format=PrivilegeEscalationGuardrailResponse,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            .choices[0]
            .message.content
        )
        response = PrivilegeEscalationGuardrailResponse.model_validate_json(response)
        return response
