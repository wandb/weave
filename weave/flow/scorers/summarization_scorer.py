from textwrap import dedent
from typing import Any, List

from pydantic import BaseModel, Field

import weave
from weave.flow.scorer.llm_scorer import InstructorLLMScorer
from weave.flow.scorer.llm_utils import create


class EntityExtractionResponse(BaseModel):
    entities: List[str] = Field(
        description="A list of unique entities extracted from the text"
    )


class SummarizationScorer(InstructorLLMScorer):
    """Estimates summary quality by computing the recall of entities in the model output compared to the input."""

    extraction_prompt: str = dedent("""
    Extract unique entities from the following text without repetition.

    Text: {text}
    Entities:
    """)

    temperature: float = 0.7
    max_tokens: int = 1024

    def extract_entities(self, text: str) -> List[str]:
        # Use LLM to extract entities
        prompt = self.extraction_prompt.format(text=text)
        response = create(
            self.client,
            messages=[{"role": "user", "content": prompt}],
            response_model=EntityExtractionResponse,
            model=self.model_id,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        entities = [e.strip().lower() for e in response.entities]
        return entities

    @weave.op
    def score(self, input: str, output: str, **kwargs: Any) -> dict:
        # Extract entities
        output_entities = self.extract_entities(output)
        input_entities = self.extract_entities(input)
        # Calculate recall
        if not output_entities:
            return {"recall": 0.0}
        matches = set(output_entities) & set(input_entities)
        recall = len(matches) / len(input_entities)
        return {"recall": recall}
