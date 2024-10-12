import asyncio
from typing import Any, List, Literal

from pydantic import BaseModel, Field

import weave
from weave.flow.scorers.llm_scorer import InstructorLLMScorer
from weave.flow.scorers.llm_utils import create

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
`excellent`: The <summary> contains all of the key information and entities in the <input>, \
is concise and information dense, is grammatically correct and doesn't contain any \
information or assertions that are not present in the <input>.

`ok`: The <summary> contains most of the key information and entities in the <input>, \
is somewhat concise and informative, is mostly grammatically correct and doesn't contain any \
information or assertions that are not present in the <input>.

`poor`: The <summary> misses most or all of the key information in the <input>, \
or is very verbose or vague, or is not concise or informative, or has many grammatical errors, \
or contains information or assertions that are not present in the <input>.
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
    entities: List[str] = Field(
        description="A list of unique entities extracted from the text."
    )


summarization_quality_options = Literal["poor", "ok", "excellent"]
summarization_quality_mapping = {"poor": 0.0, "ok": 0.5, "excellent": 1.0}


class SummarizationEvaluationResponse(BaseModel):
    think_step_by_step: str = Field(
        description="Think step-by-step about the quality of the <summary> before deciding \
on the summarization_score."
    )
    summarization_evaluation: summarization_quality_options = Field(
        description="The evaluation of the summary"
    )


class SummarizationScorer(InstructorLLMScorer):
    """
    Estimates summary quality by both:
    - Calculating the entity density of the summary, similar to how entity density is
    used in the Chain of Density paper, https://arxiv.org/abs/2309.04269.
    - Using an LLM to evaluate the summary quality.

    column_map: A `scorer parameter name : dataset column name` mapping.
    
    This summarization scorer expects the input column in the dataset to be named "input" \
        and the output column in the dataset to be named "summary".
        You can specify a different mapping in the `column_map` argument. For example, \
        if your dataset contains columns "news_article" and "news_summary" then you can \
        specify `column_map={"input": "news_article", "output": "news_summary"}`.
    
    Parameters to the `score` function
    - input: The text that was to be summarized
    - output: the summary of the text
    """

    extraction_system_prompt: str = DEFAULT_EXTRACTION_SYSTEM_PROMPT
    extraction_prompt: str = DEFAULT_EXTRACTION_USER_PROMPT
    summarization_evaluation_system_prompt: str = (
        DEFAULT_SUMMARIZATION_EVALUATION_SYSTEM_PROMPT
    )
    summarization_evaluation_prompt: str = DEFAULT_SUMMARIZATION_EVALUATION_USER_PROMPT
    fast_model_id: str = "gpt-4o-mini"
    entity_density_threshold: float = 0.08
    temperature: float = 0.7
    max_tokens: int = 1024

    @weave.op
    def extract_entities(self, text: str) -> List[str]:
        """Use an LLM to extract entities"""
        response = create(
            self.client,
            messages=[
                {"role": "system", "content": self.extraction_system_prompt},
                {"role": "user", "content": self.extraction_prompt.format(text=text)},
            ],
            response_model=EntityExtractionResponse,
            model=self.fast_model_id,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        entities = [e.strip().lower() for e in response.entities]
        return entities

    @weave.op
    def evaluate_summary(
        self, input: str, summary: str
    ) -> SummarizationEvaluationResponse:
        """Evaluate the quality of a summary using an LLM"""
        return create(
            self.client,
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
            response_model=SummarizationEvaluationResponse,
            model=self.model_id,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def simple_word_tokenize(self, text: str) -> List[str]:
        """Simple word tokenization"""
        return text.split()

    @weave.op
    async def score(self, input: str, output: str, **kwargs: Any) -> dict:
        """
        - input: the piece of text that was to be summarized
        - output: the generated summary of the input
        """
        extract_task = asyncio.to_thread(self.extract_entities, text=output)
        evaluate_task = asyncio.to_thread(
            self.evaluate_summary, input=input, summary=output
        )
        summary_entities, llm_eval = await asyncio.gather(extract_task, evaluate_task)

        # LLM evaluation
        result = {}
        result["summarization_eval_score"] = summarization_quality_mapping.get(
            llm_eval.summarization_evaluation.lower()
        )
        result["llm_eval_reasoning"] = llm_eval.think_step_by_step

        # Entity density evaluation
        summary_words = self.simple_word_tokenize(output)
        entity_density = len(summary_entities) / len(summary_words)
        result["is_entity_dense"] = entity_density >= self.entity_density_threshold
        result["entity_density"] = entity_density

        return result
