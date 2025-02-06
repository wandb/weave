from typing import TYPE_CHECKING, Any, Union

from pydantic import BaseModel, Field

import weave
from weave import Scorer
from weave.scorers.guardrails.prompts import (
    PRIVILEGE_ESCALATION_SYSTEM_PROMPT,
    PRIVILEGE_ESCALATION_USER_PROMPT,
)
from weave.scorers.llm_utils import OPENAI_DEFAULT_MODEL

if TYPE_CHECKING:
    from instructor import Instructor


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
    _client: Union["Instructor", None] = None

    def model_post_init(self, __context: Any) -> None:
        import instructor
        from litellm import completion

        self._client = instructor.from_litellm(completion)

    @weave.op
    def score(self, output: str) -> PrivilegeEscalationGuardrailResponse:
        import litellm
        from litellm import completion

        litellm.enable_json_schema_validation = True

        response = (
            completion(
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

        return PrivilegeEscalationGuardrailResponse.model_validate_json(response)
