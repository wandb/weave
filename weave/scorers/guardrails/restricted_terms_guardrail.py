from typing import TYPE_CHECKING, Any, Optional, Union

from pydantic import BaseModel, Field

import weave
from weave.scorers import Scorer
from weave.scorers.guardrails.prompts import (
    RESTRICTED_TERMS_GUARDRAIL_SYSTEM_PROMPT,
    RESTRICTED_TERMS_GUARDRAIL_USER_PROMPT,
)
from weave.scorers.llm_utils import OPENAI_DEFAULT_MODEL, create

if TYPE_CHECKING:
    from instructor import Instructor


class TermMatch(BaseModel):
    """Represents a matched term and its variations"""

    original_term: str
    matched_text: str
    match_type: str = Field(
        description="Type of match: EXACT, MISSPELLING, ABBREVIATION, or VARIANT"
    )
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

    @property
    def safe(self) -> bool:
        return not self.contains_restricted_terms


class RestrictedTermsRecognitionResponse(BaseModel):
    safe: bool
    detected_entities: list[TermMatch]
    reasoning: str
    anonymized_text: Optional[str] = None


class RestrictedTermsLLMGuardrail(Scorer):
    system_prompt: str = RESTRICTED_TERMS_GUARDRAIL_SYSTEM_PROMPT
    model_id: str = OPENAI_DEFAULT_MODEL
    temperature: float = 0.1
    max_tokens: int = 4096
    should_anonymize: bool = True
    custom_terms: list[str] = [
        "Microsoft",
        "Amazon Web Services",
        "Facebook",
        "Meta",
        "Google",
        "Salesforce",
        "Oracle",
    ]
    aggregate_redaction: bool = True
    _client: Union["Instructor", None] = None

    def model_post_init(self, __context: Any) -> None:
        import instructor
        from litellm import completion

        self._client = instructor.from_litellm(completion)

    @weave.op
    def analyse_restricted_terms(self, prompt: str) -> RestrictedTermsAnalysis:
        user_prompt = RESTRICTED_TERMS_GUARDRAIL_USER_PROMPT.format(
            text=prompt, custom_terms=", ".join(self.custom_terms)
        )
        return create(
            self._client,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=self.model_id,
            response_model=RestrictedTermsAnalysis,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    @weave.op
    def frame_guardrail_reasoning(self, analysis: RestrictedTermsAnalysis) -> str:
        if analysis.contains_restricted_terms:
            reasoning_parts = ["Restricted terms detected:"]
            for match in analysis.detected_matches:
                reasoning_parts.append(
                    f"\n- {match.original_term}: {match.matched_text} ({match.match_type})"
                )
            reasoning = "\n".join(reasoning_parts)
        else:
            reasoning = "No restricted terms detected."
        return reasoning

    @weave.op
    def get_anonymized_text(
        self, prompt: str, analysis: RestrictedTermsAnalysis
    ) -> Union[str, None]:
        anonymized_text = None
        if self.should_anonymize and analysis.contains_restricted_terms:
            anonymized_text = prompt
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
    def score(self, prompt: str) -> RestrictedTermsRecognitionResponse:
        analysis: RestrictedTermsAnalysis = self.analyse_restricted_terms(prompt)
        reasoning = self.frame_guardrail_reasoning(analysis)
        anonymized_text = self.get_anonymized_text(prompt, analysis)
        return RestrictedTermsRecognitionResponse(
            safe=not analysis.contains_restricted_terms,
            detected_entities=analysis.detected_matches,
            reasoning=reasoning,
            anonymized_text=anonymized_text,
        ).model_dump()
