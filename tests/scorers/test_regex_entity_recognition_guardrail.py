import pytest

from weave.scorers.guardrails.regex_entity_recognition_guardrail import (
    RegexEntityRecognitionGuardrail,
    RegexEntityRecognitionResponse,
)


@pytest.fixture
def regex_entity_recognition_guardrail():
    return RegexEntityRecognitionGuardrail(
        should_anonymize=True,
        custom_patterns={
            "employee_id": r"EMP\d{6}",
            "project_code": r"PRJ-[A-Z]{2}-\d{4}",
        },
    )


def test_regex_entity_recognition_guardrail(regex_entity_recognition_guardrail):
    result = regex_entity_recognition_guardrail.score(
        "EMP:123456 is assigned to PRJ-AB-1234."
    )
    # we should be able to do this validation
    _ = RegexEntityRecognitionResponse.model_validate(result)

    assert result["safe"] == False
    assert (
        result["anonymized_text"]
        == "EMP:[redacted] is [redacted] to PRJ-AB-[redacted]."
    )
