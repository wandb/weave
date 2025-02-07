from weave.scorers.guardrails.regex_entity_recognition_guardrail import (
    RegexEntityRecognitionGuardrail,
    RegexEntityRecognitionResponse,
)


def test_regex_entity_recognition_guardrail():
    result = RegexEntityRecognitionGuardrail(
        should_anonymize=True,
        patterns={
            "employee_id": r"EMP:\d{6}",
            "project_code": r"PRJ-[A-Z]{2}-\d{4}",
        },
    ).score("EMP:123456 is assigned to PRJ-AB-1234.")
    # we should be able to do this validation
    _ = RegexEntityRecognitionResponse.model_validate(result)

    assert result["flagged"] == True
    assert result["detected_entities"] == {
        "employee_id": ["EMP:123456"],
        "project_code": ["PRJ-AB-1234"],
    }
    assert result["anonymized_text"] == "[redacted] is assigned to [redacted]."
