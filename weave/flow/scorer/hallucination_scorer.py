from pydantic import BaseModel, Field


import weave
from weave.flow.scorer.utils import stringify
from weave.flow.scorer.llm_scorer import LLMScorer
from weave.flow.scorer.llm_utils import OPENAI_DEFAULT_MODEL


DEFAULT_SYSTEM_PROMPT =  """You are tasked with auditing AI agents. Your role is to evaluate conversations, ensuring that the agent's responses are plausible, factually accurate, and non-controversial based on the user's input. If the agent chooses to decline providing an answer, this should be regarded as a valid response."""
DEFAULT_USER_PROMPT =  """Given some input_data and a output, determine if the output is a hallucination of the input_data.
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
    chain_of_thought: str = Field(description="Think step by step about whether the output is a hallucination of the dataset_row")
    is_hallucination: bool = Field(description="Whether the model output is a hallucination of the dataset row")

class HallucinationScorer(LLMScorer):
    """
    Scorer that checks if the model output is a hallucination of the dataset row.
    """
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    user_prompt: str = DEFAULT_USER_PROMPT
    model_id: str = OPENAI_DEFAULT_MODEL
    temperature: float = 0.7
    max_tokens: int = 4096
    input_data_columns: list[str] = Field(description="The columns of the input data to use as ground truth")

    @weave.op
    def score(self, output: str, dataset_row: dict) -> HallucinationResponse:

        output = stringify(output)

        input_data = {k: stringify(v) for k, v in dataset_row.items() if k in self.input_data_columns}

        response = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self.user_prompt.format(input_data=input_data, output=output)},
            ],
            model=self.model_id,
            response_model=HallucinationResponse,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response


if __name__ == "__main__":
    try:
        import openai, os, weave, asyncio

        weave.init("hallucination-scorer-2")

        openai_client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        scorer = HallucinationScorer(client=openai_client, input_data_columns=["text"])

        output = "John favorite cheese is camembert"
        dataset_row = {"text": "John doesn't like cheese"}
        response = scorer.score(output, dataset_row)
        print(response)
    
        @weave.op
        def model():
            return "John favorite food is apples"

        dataset = [{"text": "John doesn't like cheese"}, 
                   {"text": "John likes pizza"}]
        
        evaluation = weave.Evaluation(dataset=dataset, scorers=[scorer])
        asyncio.run(evaluation.evaluate(model))
    
    except Exception as e:
        print(e)
    