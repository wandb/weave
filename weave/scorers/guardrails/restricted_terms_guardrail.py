import warnings
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field

import weave
from weave import Scorer
from weave.scorers.default_models import OPENAI_DEFAULT_MODEL
from weave.scorers.guardrails.prompts import (
    RESTRICTED_TERMS_GUARDRAIL_SYSTEM_PROMPT,
    RESTRICTED_TERMS_GUARDRAIL_USER_PROMPT,
)


class TermMatch(BaseModel):
    """Represents a matched term and its variations"""

    original_term: str
    matched_text: str
    match_type: Literal["EXACT", "MISSPELLING", "ABBREVIATION", "VARIANT"]
    explanation: str = Field(
        description="Explanation of why this is considered a match"
    )


class RestrictedTermsAnalysis(BaseModel):
    """Analysis result for restricted terms detection"""

    contains_restricted_terms: bool = Field(
        description="Whether any restricted terms were detected"
    )
    detected_matches: list[TermMatch] = Field(
        default_factory=list,
        description="List of detected term matches with their variations",
    )
    explanation: str = Field(description="Detailed explanation of the analysis")
    anonymized_text: Optional[str] = Field(
        default=None,
        description="Text with restricted terms replaced with category tags",
    )


class RestrictedTermsRecognitionResponse(BaseModel):
    """Response from the `RestrictedTermsLLMGuardrail`"""

    flagged: bool
    detected_entities: list[TermMatch]
    reason: str
    anonymized_text: Optional[str] = None


class RestrictedTermsLLMGuardrail(Scorer):
    """A guardrail to detect and analyze restricted terms and their variations in a given
    text prompt using an LLM.

    Attributes:
        custom_terms (list[str]): The list of custom terms to detect.
        system_prompt (str): The prompt describing the task of detecting restricted terms.
        user_prompt (str): The prompt template to pass the input and output data. The template must
            contain placeholders for both `{text}` and `{custom_terms}`.
        model_id (str): The LLM model name, depends on the LLM's providers to be used `client` being used.
        temperature (float): LLM temperature setting.
        max_tokens (int): Maximum number of tokens in the LLM's response.
        should_anonymize (bool): Whether to anonymize the text.
    """

    custom_terms: list[str]
    system_prompt: str = RESTRICTED_TERMS_GUARDRAIL_SYSTEM_PROMPT
    user_prompt: str = RESTRICTED_TERMS_GUARDRAIL_USER_PROMPT
    model_id: str = OPENAI_DEFAULT_MODEL
    temperature: float = 0.1
    max_tokens: int = 4096
    should_anonymize: bool = True
    aggregate_redaction: bool = True

    def model_post_init(self, __context: Any) -> None:
        if self.model_id not in ["gpt-4o", "gpt-4o-mini", "o1", "o1-preview"]:
            warnings.warn(
                "The default system prompt is optimized for gpt-4o and gpt-4o-mini. Using a different model may lead to unexpected results."
            )

    @weave.op
    async def analyse_restricted_terms(self, output: str) -> RestrictedTermsAnalysis:
        from litellm import acompletion

        response = await acompletion(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": self.user_prompt.format(
                        text=output, custom_terms=", ".join(self.custom_terms)
                    ),
                },
            ],
            model=self.model_id,
            response_format=RestrictedTermsAnalysis,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return RestrictedTermsAnalysis.model_validate_json(
            response.choices[0].message.content
        )

    def frame_guardrail_reasoning(self, analysis: RestrictedTermsAnalysis) -> str:
        if analysis.contains_restricted_terms:
            reasoning_parts = ["Restricted terms detected:"]
            for match in analysis.detected_matches:
                reasoning_parts.append(
                    f"\n- {match.original_term}: {match.matched_text} ({match.match_type})"
                )
            return "\n".join(reasoning_parts)
        return "No restricted terms detected."

    @weave.op
    def get_anonymized_text(
        self, output: str, analysis: RestrictedTermsAnalysis
    ) -> Union[str, None]:
        anonymized_text = None
        if self.should_anonymize and analysis.contains_restricted_terms:
            anonymized_text = output
            for match in analysis.detected_matches:
                replacement = (
                    "[redacted]"
                    if self.aggregate_redaction
                    else f"[{match.match_type.upper()}]"
                )
                anonymized_text = anonymized_text.replace(
                    match.matched_text, replacement
                )
        return anonymized_text

    @weave.op
    async def score(self, output: str) -> RestrictedTermsRecognitionResponse:
        analysis: RestrictedTermsAnalysis = await self.analyse_restricted_terms(output)
        reasoning = self.frame_guardrail_reasoning(analysis)
        anonymized_text = self.get_anonymized_text(output, analysis)
        return RestrictedTermsRecognitionResponse(
            flagged=analysis.contains_restricted_terms,
            detected_entities=analysis.detected_matches,
            reason=reasoning,
            anonymized_text=anonymized_text,
        ).model_dump()
