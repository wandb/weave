import asyncio
from typing import Any, Literal

from pydantic import BaseModel, Field

import weave
from weave.scorers.default_models import OPENAI_DEFAULT_MODEL
from weave.scorers.scorer_types import LLMScorer

DEFAULT_EXTRACTION_SYSTEM_PROMPT = """
Given a <text>, extract all the unique entities from the text without repetition.
"""

DEFAULT_EXTRACTION_USER_PROMPT = """
Extract all the unique entities from the following <text> without repetition:
<text>
{text}
</text>
"""

DEFAULT_SUMMARIZATION_EVALUATION_SYSTEM_PROMPT = """
Given an <input> and a <summary>, evaluate the quality of the <summary>.

# Considerations
- Does the <summary> contain the key information in the <input>?
- Is the <summary> concise and informative?
- Is the <summary> grammatically correct?
- Does the <summary> contain information or assertions that are not present in the <input>?

# Scoring Rubric
`excellent`: The <summary> contains all of the key information and entities in the <input>, is concise and informative, is grammatically correct and doesn't contain any information or assertions that are not present in the <input>.

`ok`: The <summary> contains most of the key information and entities in the <input>, is somewhat concise and informative, is mostly grammatically correct and doesn't contain any information or assertions that are not present in the <input>.

`poor`: The <summary> misses most or all of the key information in the <input>, or is very verbose or vague, or is not concise or informative, or has many grammatical errors, or contains information or assertions that are not present in the <input>.
"""

DEFAULT_SUMMARIZATION_EVALUATION_USER_PROMPT = """
Evaluate the quality of the following <summary> given the <input>:

<input>
{input}
</input>

<summary>
{summary}
</summary>
"""


class EntityExtractionResponse(BaseModel):
    entities: list[str] = Field(
        description="A list of unique entities extracted from the text."
    )


summarization_quality_options = Literal["poor", "ok", "excellent"]
summarization_quality_mapping = {"poor": 0.0, "ok": 0.5, "excellent": 1.0}


class SummarizationEvaluationResponse(BaseModel):
    think_step_by_step: str = Field(
        description="Think step-by-step about the quality of the <summary> before deciding on the summarization score."
    )
    summarization_evaluation: summarization_quality_options = Field(
        description="The evaluation of the summary ('poor', 'ok', or 'excellent')."
    )


class SummarizationScorer(LLMScorer):
    """
    A Scorer that evaluates the quality of summaries in two ways:
      - It uses an LLM to calculate the entity density of the summary, which is a rough measure of how
        information-dense the summary is. This method evaluates whether the summary contains a sufficient
        number of key entities relative to its length.
      - It leverages another LLM evaluation to grade the summary quality on a scale of 'poor', 'ok', to 'excellent'.
        These grades are then mapped to numerical scores ({'poor': 0.0, 'ok': 0.5, 'excellent': 1.0}), allowing
        aggregate performance calculations on a dataset of summaries.

    The LLM evaluator's behavior can be customized by modifying the `summarization_evaluation_system_prompt` and
    `summarization_evaluation_prompt` attributes, thus tailoring the definition of a good summary.

    Note:
      - This scorer uses the LLM via litellm.acompletion to generate structured outputs from the LLM provider's response.
      - The `score` method expects the input column from the dataset to be named "input". If your dataset column has a
        different name, you can specify a different mapping using the `column_map` argument when initializing the scorer,
        for example: `column_map={"input": "news_article"}`.

    Attributes:
      extraction_system_prompt (str): System prompt used to extract distinct entities from the input.
      extraction_prompt (str): Template prompt for entity extraction; must contain a `{text}` placeholder.
      summarization_evaluation_system_prompt (str): System prompt that defines how to evaluate the quality of a summary.
      summarization_evaluation_prompt (str): Template prompt for summarization evaluation; must include `{input}` and `{summary}`.
      entity_density_threshold (float): Threshold for determining if a summary is sufficiently entity-dense.
      model_id (str): Identifier for the LLM model to be used.
      temperature (float): LLM temperature setting.
      max_tokens (int): Maximum number of tokens in the LLM's response.

    Methods:
      score(input: str, output: str) -> dict:
          Calculates both the LLM evaluation score (by mapping 'poor', 'ok', 'excellent' to numerical values) and
          the entity density score of the summary.
    """

    extraction_system_prompt: str = DEFAULT_EXTRACTION_SYSTEM_PROMPT
    extraction_prompt: str = DEFAULT_EXTRACTION_USER_PROMPT
    summarization_evaluation_system_prompt: str = (
        DEFAULT_SUMMARIZATION_EVALUATION_SYSTEM_PROMPT
    )
    summarization_evaluation_prompt: str = DEFAULT_SUMMARIZATION_EVALUATION_USER_PROMPT
    entity_density_threshold: float = 0.08
    model_id: str = OPENAI_DEFAULT_MODEL
    temperature: float = Field(
        default=0.7,
        description="Controls randomness in the LLM's responses (0.0 to 1.0)",
    )
    max_tokens: int = Field(
        default=1024,
        description="Maximum number of tokens allowed in the LLM's response",
    )

    @weave.op
    async def _extract_entities(self, text: str) -> list[str]:
        """Use an LLM to extract unique entities from the provided text."""
        response = await self._acompletion(
            messages=[
                {"role": "system", "content": self.extraction_system_prompt},
                {"role": "user", "content": self.extraction_prompt.format(text=text)},
            ],
            response_format=EntityExtractionResponse,
            model=self.model_id,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        response = EntityExtractionResponse.model_validate_json(
            response.choices[0].message.content
        )
        entities = [e.strip().lower() for e in response.entities]
        return entities

    @weave.op
    async def _evaluate_summary(
        self, input: str, summary: str
    ) -> SummarizationEvaluationResponse:
        """Evaluate the quality of a summary using an LLM."""
        response = await self._acompletion(
            messages=[
                {
                    "role": "system",
                    "content": self.summarization_evaluation_system_prompt,
                },
                {
                    "role": "user",
                    "content": self.summarization_evaluation_prompt.format(
                        input=input, summary=summary
                    ),
                },
            ],
            response_format=SummarizationEvaluationResponse,
            model=self.model_id,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return SummarizationEvaluationResponse.model_validate_json(
            response.choices[0].message.content
        )

    def _simple_word_tokenize(self, text: str) -> list[str]:
        """Simple word tokenization: splits text into words."""
        return text.split()

    @weave.op
    async def score(self, *, input: str, output: str, **kwargs: Any) -> dict:
        """
        Evaluate a summary by combining entity density and LLM quality evaluation.

        This method performs two assessments:
          1. Entity Density Evaluation: Extracts entities from the summary and calculates the ratio of extracted entities
             to the total number of words. Determines if the summary is dense enough based on the `entity_density_threshold`.
          2. LLM Evaluation: Uses an LLM to assess the quality of the summary, mapping the evaluation ('poor', 'ok', or
             'excellent') to a numerical score.

        Returns:
            A dictionary with:
              - "summarization_eval_score": The numerical score based on LLM evaluation.
              - "llm_eval_reasoning": The detailed reasoning from the LLM evaluation.
              - "is_entity_dense": A boolean indicating if the summary meets the entity density threshold.
              - "entity_density": The calculated entity density ratio.
        """
        extract_task = self._extract_entities(text=str(output))
        evaluate_task = self._evaluate_summary(input=str(input), summary=str(output))
        summary_entities, llm_eval = await asyncio.gather(extract_task, evaluate_task)

        result = {}
        result["summarization_eval_score"] = summarization_quality_mapping.get(
            llm_eval.summarization_evaluation.lower()
        )
        result["llm_eval_reasoning"] = llm_eval.think_step_by_step

        summary_words = self._simple_word_tokenize(output)
        entity_density = len(summary_entities) / len(summary_words)
        result["is_entity_dense"] = entity_density >= self.entity_density_threshold
        result["entity_density"] = entity_density

        return result
