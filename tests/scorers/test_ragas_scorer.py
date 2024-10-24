import pytest
from openai import OpenAI

from weave.scorers import (
    ContextEntityRecallScorer,
    ContextRelevancyScorer,
)
from weave.scorers.ragas_scorer import (
    EntityExtractionResponse,
    RelevancyResponse,
)


# Mock the create function
@pytest.fixture
def mock_create(monkeypatch):
    def _mock_create(*args, **kwargs):
        # Retrieve the response_model to return appropriate mock responses
        response_model = kwargs.get("response_model")
        if response_model is EntityExtractionResponse:
            return EntityExtractionResponse(entities=["Paris"])
        elif response_model is RelevancyResponse:
            return RelevancyResponse(
                reasoning="The context directly answers the question.",
                relevancy_score=1,
            )

    monkeypatch.setattr("weave.scorers.ragas_scorer.create", _mock_create)


@pytest.fixture
def context_entity_recall_scorer(mock_create):
    return ContextEntityRecallScorer(
        client=OpenAI(api_key="DUMMY_API_KEY"),
        model_id="gpt-4o",
        temperature=0.7,
        max_tokens=1024,
    )


@pytest.fixture
def context_relevancy_scorer(mock_create):
    return ContextRelevancyScorer(
        client=OpenAI(api_key="DUMMY_API_KEY"),
        model_id="gpt-4o",
        temperature=0.7,
        max_tokens=1024,
    )


def test_context_entity_recall_scorer_score(context_entity_recall_scorer):
    output = "Paris is the capital of France."
    context = "The capital city of France is Paris."
    result = context_entity_recall_scorer.score(output, context)
    assert isinstance(result, dict)
    assert "recall" in result
    assert result["recall"] == 1.0  # Assuming full recall in mock response


def test_context_relevancy_scorer_score(context_relevancy_scorer):
    output = "What is the capital of France?"
    context = "Paris is the capital city of France."
    result = context_relevancy_scorer.score(output, context)
    assert isinstance(result, dict)
    assert "relevancy_score" in result
    assert result["relevancy_score"] == 1  # Assuming relevancy in mock response
