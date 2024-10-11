import pytest
from openai import OpenAI

from weave.flow.scorer.summarization_scorer import (
    EntityExtractionResponse,
    SummarizationScorer,
)


# Mock the OpenAI client
class MockOpenAI(OpenAI):
    pass

# mock the create function
@pytest.fixture
def mock_create(monkeypatch):
    def _mock_create(*args, **kwargs):
        return EntityExtractionResponse(
            entities=["entity1", "entity2"]
        )
    monkeypatch.setattr('weave.flow.scorer.summarization_scorer.create', _mock_create)

@pytest.fixture
def summarization_scorer(mock_create):
    return SummarizationScorer(client=MockOpenAI(), model_id="gpt-4o", temperature=0.7, max_tokens=1024)

def test_summarization_scorer_initialization(summarization_scorer, mock_create):
    assert isinstance(summarization_scorer, SummarizationScorer)
    assert summarization_scorer.model_id == "gpt-4o"
    assert summarization_scorer.temperature == 0.7
    assert summarization_scorer.max_tokens == 1024

def test_summarization_scorer_extract_entities(summarization_scorer, mock_create):
    text = "This is a sample text with entities."
    entities = summarization_scorer.extract_entities(text)
    assert isinstance(entities, list)
    assert len(entities) == 2
    assert "entity1" in entities
    assert "entity2" in entities

def test_summarization_scorer_score(summarization_scorer):
    input_text = "This is the original text with entities."
    output_text = "This is a summary with some entities."
    result = summarization_scorer.score(input=input_text, output=output_text)
    assert isinstance(result, dict)
    assert "recall" in result
    assert 0 <= result["recall"] <= 1

# Add more tests as needed
