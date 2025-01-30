import pytest

from weave.scorers.guardrails.restricted_terms_guardrail import (
    RestrictedTermsAnalysis,
    RestrictedTermsLLMGuardrail,
    RestrictedTermsRecognitionResponse,
    TermMatch,
)


@pytest.fixture
def mock_create(monkeypatch):
    def _mock_create(*args, **kwargs):
        return RestrictedTermsAnalysis(
            contains_restricted_terms=True,
            detected_matches=[
                TermMatch(
                    original_term="Microsoft",
                    matched_text="Microsoft",
                    match_type="EXACT",
                    explanation="The term 'Microsoft' is an exact match to the restricted term 'Microsoft'.",
                )
            ],
            explanation="""Restricted terms detected:

- Microsoft: Microsoft (EXACT)""",
            anonymized_text="Hello, my name is [redacted].",
        )

    monkeypatch.setattr("weave.scorers.llm_utils.create", _mock_create)


@pytest.fixture
def restricted_terms_recognition_llm_guardrail(mock_create):
    return RestrictedTermsLLMGuardrail()


def test_restricted_terms_guardrail_score(
    restricted_terms_recognition_llm_guardrail, mock_create
):
    result = restricted_terms_recognition_llm_guardrail.score(
        "Hello, my name is Microsoft."
    )
    _ = RestrictedTermsRecognitionResponse.model_validate(result)
    assert result["safe"] == False
    assert (
        result["reasoning"]
        == """Restricted terms detected:

- Microsoft: Microsoft (EXACT)"""
    )
    assert result["anonymized_text"] == "Hello, my name is [redacted]."
