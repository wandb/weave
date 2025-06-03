import json
from typing import Any, Union

import jsonschema
from pydantic import BaseModel, Field

from weave.flow.scorer import Scorer
from weave.trace.op import op


class LLMAsAJudgeScorer(Scorer):
    """
    A scorer that uses a large language model (LLM) to evaluate the output of
    another system or LLM. This is often referred to as "LLM as a Judge".

    The scorer works by sending a prompt to an LLM, which includes the output
    to be scored. The LLM's response is then parsed according to a specified
    `response_format` (either a JSON schema or a Pydantic model) to extract
    the score and any other relevant information.

    Attributes:
        system_prompt: The system prompt to guide the behavior of the scoring LLM.
        scorer_prompt: The user prompt template for the scoring LLM. This prompt
                       should include a placeholder for the `output` to be scored,
                       e.g., "Please score the following output: {output}".
        model: The identifier of the LLM to be used for scoring (e.g., "gpt-3.5-turbo").
        response_format: Defines the expected structure of the LLM's response.
                         This can be a JSON schema (as a dictionary) or a Pydantic
                         BaseModel subclass. The LLM's output will be validated
                         against this format.

    Methods:
        score(output: str) -> dict[str, Any]:
            Scores the output of a system or LLM using the LLM as a judge.

    Args:
                output: The output to be scored.

    Returns:
                dict[str, Any]: A dictionary containing the output of the LLM with schema compliant with response_format.
    """

    system_prompt: str = Field(description="The system prompt for the scorer LLM.")
    scorer_prompt: str = Field(description="The scorer prompt for the scorer LLM.")
    model: str = Field(description="The scoring model to use to scorer outputs.")
    response_format: Union[dict, type[BaseModel]] = Field(
        description="The response format for the scorer LLM."
    )

    @op
    async def score(self, *, input: Any, output: Any, **kwargs: Any) -> dict[str, Any]:
        if isinstance(self.model, str):
            try:
                from litellm import acompletion
            except ImportError:
                raise ImportError(
                    "litellm is required to use the LLM-powered scorers, please install it with `pip install litellm`"
                )

            response = await acompletion(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {
                        "role": "user",
                        "content": self.scorer_prompt.format(
                            input=input, output=output
                        ),
                    },
                ],
                model=self.model,
                response_format=self.response_format,
                temperature=0,
            )

            content = response.choices[0].message.content
        else:
            # elif isinstance(self.model, PlaygroundLLM)
            raise NotImplementedError()

        final_response: dict[str, Any]

        if isinstance(self.response_format, dict):
            # response_format is in JSONSchema format
            final_response = json.loads(content)
            jsonschema.validate(final_response, self.response_format)

        elif issubclass(self.response_format, BaseModel):
            # response_format is a Pydantic model
            validated_content = self.response_format.model_validate_json(content)
            final_response = validated_content.model_dump()

        return final_response
