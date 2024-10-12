from pydantic import BaseModel, Field

import weave
from weave.flow.scorer.llm_scorer import InstructorLLMScorer
from weave.flow.scorer.llm_utils import OPENAI_DEFAULT_MODEL, create
from weave.flow.scorer.utils import stringify

DEFAULT_SYSTEM_PROMPT = """You are tasked with auditing AI agents. Your role is to evaluate conversations, ensuring that the agent's responses are plausible, factually accurate, and non-controversial based on the user's input. If the agent chooses to decline providing an answer, this should be regarded as a valid response."""
DEFAULT_USER_PROMPT = """Given some input_data and a output, determine if the output is a hallucination of the input_data.
## Input data
<input_data>
{input_data}
</dataset_row>

## Model output
<output>
{output}
</output>

## Instructions
Think step by step before answering. Is the output an factually and logically consistent with the input_data?
"""


class HallucinationResponse(BaseModel):
    chain_of_thought: str = Field(
        description="Think step by step about whether the output is a hallucination of the dataset_row"
    )
    is_hallucination: bool = Field(
        description="Whether the model output is a hallucination of the dataset row"
    )


class HallucinationScorer(InstructorLLMScorer):
    """Scorer that checks if the model output is a hallucination of the dataset row."""

    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    user_prompt: str = DEFAULT_USER_PROMPT
    model_id: str = OPENAI_DEFAULT_MODEL
    temperature: float = 0.7
    max_tokens: int = 4096

    @weave.op
    def score(self, output: str, context: str) -> HallucinationResponse:
        output = stringify(output)
        response = create(
            self.client,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": self.user_prompt.format(
                        input_data=context, output=output
                    ),
                },
            ],
            model=self.model_id,
            response_model=HallucinationResponse,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response
