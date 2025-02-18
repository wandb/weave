import pytest

from weave.scorers import PresidioScorer


@pytest.fixture
def presidio_entity_recognition_guardrail():
    return PresidioScorer()


@pytest.mark.skip(
    reason="This test depends on the spacy model `en-core-web-lg` which takes a long time to download"
)
def test_presidio_entity_recognition_guardrail_score(
    presidio_entity_recognition_guardrail,
):
    input_text = "John Doe is a software engineer at XYZ company and his email is john.doe@xyz.com."
    result = presidio_entity_recognition_guardrail.score(input_text)
    assert not result.passed
    assert "john.doe@xyz.com" in result.metadata["detected_entities"]["EMAIL_ADDRESS"]
