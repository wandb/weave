import asyncio
from typing import Literal, TypedDict, cast

from litellm import acompletion
from pydantic import BaseModel, Field

import weave
from weave.scorers.llm_scorer import LLMScorer
from weave.scorers.llm_utils import OPENAI_DEFAULT_MODEL

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
    entities: list[str] = Field(
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


class SummarizationScorerOutput(TypedDict):
    """Output type for SummarizationScorer."""

    summarization_eval_score: float
    llm_eval_reasoning: str
    is_entity_dense: bool
    entity_density: float


class SummarizationScorer(LLMScorer):
    """
    A Scorer that evaluates the quality of summaries in two ways:
        - using an LLM to calculate the entity density of the summary, similar to how entity density is
        used in the Chain of Density paper, https://arxiv.org/abs/2309.04269. This is a rough measure for
        how information-dense the summary is.
        - using another LLM evaluator to grade the summary quality from `poor`, `ok`, to `excellent`. These
        grades are then mapped to numerical scores, {`poor`: 0.0, `ok`: 0.5, `excellent`: 1.0}, in order to
        be able to calculate an average score across a dataset of summaries if needed.

    To customise the LLM evaluator you can customise the `summarization_evaluation_system_prompt`and
    `summarization_evaluation_prompt` attributes to be tailored your specific definition of what a good summary
    should look like.

    Note:
        - This Scorer uses the `InstructorLLMScorer` class to generate structured outputs from the LLM
        provider's response; you will have to install the `instructor` python package to use it.
        - The `score` method expects the input column from the dataset to be named "input". If your dataset
        column has a different name, you can specify a different mapping using the `column_map` argument in the
        init of SummarizationScorer by passing `column_map={"input": "news_article"}`.

    Attributes:
        extraction_system_prompt (str): System prompt to extract the distinct entities in the input. Customising
        this can help ensure that the LLM identifies the `entities` that you care about.
        extraction_prompt (str): Prompt template for entity extraction; must contain a `{text}` placeholder.
        summarization_evaluation_system_prompt (str): System prompt defining how to evaluate the quality of a summary.
            Asks an LLM to grade the summary from `poor`, `ok`, to `excellent` and provide a rationale for the grade.
        summarization_evaluation_prompt (str): Prompt template for summarization evaluation instruction; must contain
            `{input}` and `{summary}` placeholders.
        entity_density_threshold (float): Threshold for determining if a summary is sufficiently entity-dense.
        model_id (str): The LLM model name, depends on the LLM's providers to be used `client` being used.
        temperature (float): LLM temperature setting.
        max_tokens (int): Maximum number of tokens in the LLM's response.

    Methods:
        extract_entities(text: str) -> list[str]:
            Uses an LLM to extract unique entities from the text.

        evaluate_summary(input: str, summary: str) -> SummarizationEvaluationResponse:
            Evaluates the quality of a summary using an LLM.

        score(input: str, output: str) -> dict:
            Calculates summarization score and entity density score for the given input and output.
    """

    extraction_system_prompt: str = DEFAULT_EXTRACTION_SYSTEM_PROMPT
    extraction_prompt: str = DEFAULT_EXTRACTION_USER_PROMPT
    summarization_evaluation_system_prompt: str = (
        DEFAULT_SUMMARIZATION_EVALUATION_SYSTEM_PROMPT
    )
    summarization_evaluation_prompt: str = DEFAULT_SUMMARIZATION_EVALUATION_USER_PROMPT
    entity_density_threshold: float = 0.08
    model_id: str = OPENAI_DEFAULT_MODEL
    temperature: float = 0.7
    max_tokens: int = 1024

    @weave.op
    async def extract_entities(self, text: str) -> list[str]:
        """Use an LLM to extract entities"""
        response = await acompletion(
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
    async def evaluate_summary(
        self, input: str, summary: str
    ) -> SummarizationEvaluationResponse:
        """Evaluate the quality of a summary using an LLM"""
        response = await acompletion(
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

    def simple_word_tokenize(self, text: str) -> list[str]:
        """Simple word tokenization"""
        return text.split()

    @weave.op
    async def score(self, input: str, output: str) -> SummarizationScorerOutput:
        extract_task = self.extract_entities(text=str(output))
        evaluate_task = self.evaluate_summary(input=str(input), summary=str(output))
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

        return cast(SummarizationScorerOutput, result)
