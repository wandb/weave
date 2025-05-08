# implementing metrics from ragas: https://github.com/explodinggradients/ragas

from textwrap import dedent
from typing import Any

from pydantic import BaseModel, Field

import weave
from weave.scorers.default_models import OPENAI_DEFAULT_MODEL
from weave.scorers.scorer_types import LLMScorer


class EntityExtractionResponse(BaseModel):
    entities: list[str] = Field(
        description="A list of unique entities extracted from the text"
    )


class ContextEntityRecallScorer(LLMScorer):
    """
    A Scorer that estimates context recall by extracting entities from both the model output
    and the context, then computing the recall score between them.

    Note:
        - This Scorer uses the LLM via litellm.acompletion to generate structured responses.
        - The `score` method expects two arguments: 'output' (the model's response) and 'context'
          (the reference text). If your dataset columns have different names, use the `column_map`
          argument when initializing the scorer.
        - Entity extraction is performed using an LLM, so results may vary based on the model used.

    Attributes:
        extraction_prompt (str): The prompt template used to extract entities from text. Must
          contain a {text} placeholder.
        model_id (str): The LLM model name, depending on the LLM provider being used.
        temperature (float): Controls randomness in the LLM's responses (0.0 to 1.0).
        max_tokens (int): Maximum number of tokens allowed in the LLM's response.

    Methods:
        score(output: str, context: str) -> dict:
            Computes the recall score by comparing entities in the output against those in the context.
            Returns a dict with a 'recall' key containing the score (0.0 to 1.0).
    """

    extraction_prompt: str = dedent("""
    Extract unique entities from the following text without repetition.

    Text: {text}
    Entities:
    """)
    model_id: str = OPENAI_DEFAULT_MODEL
    temperature: float = Field(
        default=0.7,
        description="Controls randomness in the LLM's responses (0.0 to 1.0)",
    )
    max_tokens: int = Field(
        default=4096,
        description="Maximum number of tokens allowed in the LLM's response",
    )

    async def _extract_entities(self, text: str) -> list[str]:
        # Use LLM to extract entities
        prompt = self.extraction_prompt.format(text=text)
        response = await self._acompletion(
            messages=[{"role": "user", "content": prompt}],
            response_format=EntityExtractionResponse,
            model=self.model_id,
        )
        response = EntityExtractionResponse.model_validate_json(
            response.choices[0].message.content
        )
        # Assume entities are returned as a comma-separated list
        entities = [e.strip() for e in response.entities]
        return entities

    @weave.op
    async def score(self, *, output: str, context: str, **kwargs: Any) -> dict:
        expected_entities = await self._extract_entities(output)
        context_entities = await self._extract_entities(context)
        # Calculate recall
        if not expected_entities:
            return {"recall": 0.0}
        matches = set(expected_entities) & set(context_entities)
        recall = len(matches) / len(expected_entities)
        return {"recall": recall}


class RelevancyResponse(BaseModel):
    reasoning: str = Field(
        description="Think step by step about whether the context is relevant to the question"
    )
    relevancy_score: int = Field(
        description="The relevancy score of the context to the question (0 for not relevant, 1 for relevant)"
    )


class ContextRelevancyScorer(LLMScorer):
    """
    A Scorer that evaluates the relevancy of the provided context to the model output using an LLM.

    Note:
        - This Scorer uses the LLM via litellm.acompletion to generate structured responses.
        - The `score` method expects two arguments: 'output' (treated as the question) and 'context'
          (the reference text). If your dataset columns have different names, use the `column_map`
          argument when initializing the scorer.
        - The relevancy score is binary (0 or 1) where 1 indicates relevant context.

    Attributes:
        relevancy_prompt (str): The prompt template used to evaluate context relevancy. Must
          contain placeholders for both {question} and {context}.
        model_id (str): The LLM model name, depending on the LLM provider being used.
        temperature (float): Controls randomness in the LLM's responses (0.0 to 1.0).
        max_tokens (int): Maximum number of tokens allowed in the LLM's response.

    Methods:
        score(output: str, context: str) -> dict:
            Evaluates the relevancy of the context to the output/question.
            Returns a dict with 'relevancy_score' (0 or 1) and 'reasoning' keys.
    """

    relevancy_prompt: str = dedent("""
    Given the following question and context, rate the relevancy of the context to the question on a scale from 0 to 1.

    Question: {question}
    Context: {context}
    Relevancy Score (0-1):
    """)
    model_id: str = OPENAI_DEFAULT_MODEL
    temperature: float = Field(
        default=0.7,
        description="Controls randomness in the LLM's responses (0.0 to 1.0)",
    )
    max_tokens: int = Field(
        default=4096,
        description="Maximum number of tokens allowed in the LLM's response",
    )

    @weave.op
    async def score(self, *, output: str, context: str, **kwargs: Any) -> dict:
        prompt = self.relevancy_prompt.format(question=output, context=context)
        response = await self._acompletion(
            messages=[{"role": "user", "content": prompt}],
            response_format=RelevancyResponse,
            model=self.model_id,
        )
        response = RelevancyResponse.model_validate_json(
            response.choices[0].message.content
        )
        return response.model_dump()
