import pytest
from pydantic import BaseModel

from weave.scorers import (
    ContextEntityRecallScorer,
    ContextRelevancyScorer,
)
from weave.scorers.ragas_scorer import (
    EntityExtractionResponse,
    RelevancyResponse,
)


# Mock the acompletion function
@pytest.fixture
def mock_acompletion(monkeypatch):
    async def _mock_acompletion(*args, **kwargs):
        response_format = kwargs.get("response_format")
        if response_format is EntityExtractionResponse:
            content = '{"entities": ["Paris"]}'
        elif response_format is RelevancyResponse:
            content = '{"reasoning": "The context directly answers the question.", "relevancy_score": 1}'

        class Message(BaseModel):
            content: str

        class Choice(BaseModel):
            message: Message

        class Response(BaseModel):
            choices: list[Choice]

        return Response(choices=[Choice(message=Message(content=content))])

    monkeypatch.setattr("weave.scorers.ragas_scorer.acompletion", _mock_acompletion)


@pytest.fixture
def context_entity_recall_scorer(mock_acompletion):
    return ContextEntityRecallScorer(
        model_id="gpt-4o",
        temperature=0.7,
        max_tokens=1024,
    )


@pytest.fixture
def context_relevancy_scorer(mock_acompletion):
    return ContextRelevancyScorer(
        model_id="gpt-4o",
        temperature=0.7,
        max_tokens=1024,
    )


@pytest.mark.asyncio
async def test_context_entity_recall_scorer_score(context_entity_recall_scorer):
    output = "Paris is the capital of France."
    context = "The capital city of France is Paris."
    result = await context_entity_recall_scorer.score(output, context)
    assert isinstance(result, dict)
    assert "recall" in result
    assert result["recall"] == 1.0  # Assuming full recall in mock response


@pytest.mark.asyncio
async def test_context_relevancy_scorer_score(context_relevancy_scorer):
    output = "What is the capital of France?"
    context = "Paris is the capital city of France."
    result = await context_relevancy_scorer.score(output, context)
    assert isinstance(result, dict)
    assert "relevancy_score" in result
    assert result["relevancy_score"] == 1  # Assuming relevancy in mock response
