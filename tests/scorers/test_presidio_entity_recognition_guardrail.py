import pytest

from weave.scorers.guardrails.presidio_entity_recognition_guardrail import (
    PresidioEntityRecognitionGuardrail,
    PresidioEntityRecognitionResponse,
)


@pytest.fixture
def presidio_entity_recognition_guardrail():
    return PresidioEntityRecognitionGuardrail(selected_entities=["EMAIL_ADDRESS"])


def test_presidio_entity_recognition_guardrail_score(
    presidio_entity_recognition_guardrail,
):
    result = presidio_entity_recognition_guardrail.score("Email: test@example.com")
    _ = PresidioEntityRecognitionResponse.model_validate(result)
    assert result["flagged"] == True
    assert result["detected_entities"] == {"EMAIL_ADDRESS": ["test@example.com"]}
    assert (
        result["reason"]
        == "Found the following entities in the text:\n- EMAIL_ADDRESS: 1 instance(s)\n\nChecked for these entity types:\n- EMAIL_ADDRESS"
    )
    assert result["anonymized_text"] == "Email: <EMAIL_ADDRESS>"
