import pytest
from weave.scorers.guardrails.presidio_entity_recognition_guardrail import (
    PresidioEntityRecognitionGuardrail,
)


@pytest.fixture
def presidio_entity_recognition_guardrail():
    return PresidioEntityRecognitionGuardrail()


def test_presidio_entity_recognition_guardrail_score(presidio_entity_recognition_guardrail):
    input_text = "John Doe is a software engineer at XYZ company and his email is john.doe@xyz.com."
    result = presidio_entity_recognition_guardrail.score(input_text)
    assert not result.passed
    assert "john.doe@xyz.com" in result.metadata["detected_entities"]["EMAIL_ADDRESS"]
