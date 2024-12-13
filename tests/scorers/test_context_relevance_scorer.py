"""Tests for the Context Relevance Scorer."""
import pytest
from unittest.mock import MagicMock
from weave.scorers.context_relevance_scorer import ContextRelevanceScorer
from tests.scorers.test_utils import generate_large_text, generate_context_and_output


@pytest.fixture
def context_relevance_scorer(monkeypatch):
    """Create a context relevance scorer for testing."""
    # Mock wandb login and project
    monkeypatch.setattr("wandb.login", lambda *args, **kwargs: True)
    mock_project = MagicMock()
    monkeypatch.setattr("wandb.Api", lambda: MagicMock(project=lambda *args: mock_project))

    scorer = ContextRelevanceScorer(
        model_name_or_path="wandb/relevance_scorer",
        device="cpu",
        name="test-context-relevance",
        description="Test context relevance scorer",
        column_map={"output": "text", "context": "context"}
    )

    def mock_pipeline(*args, **kwargs):
        def inner(text, **kwargs):
            return [{"generated_text": '{"relevance": 4, "relevant": true}'}]
        return inner

    monkeypatch.setattr("transformers.pipeline", mock_pipeline)
    monkeypatch.setattr(scorer, "_classifier", mock_pipeline())
    return scorer


@pytest.mark.asyncio
async def test_context_relevance_scorer_basic(context_relevance_scorer):
    """Test basic functionality of the context relevance scorer."""
    query = "What is the capital of France?"
    context = "Paris is the capital of France. It is known for the Eiffel Tower."
    output = "The capital of France is Paris."

    result = await context_relevance_scorer.score(
        query=query,
        context=context,
        output=output,
        verbose=True
    )

    assert "flagged" in result
    assert "extras" in result
    assert "score" in result["extras"]
    assert "all_spans" in result["extras"]


@pytest.mark.asyncio
async def test_context_relevance_scorer_large_input(context_relevance_scorer):
    """Test the context relevance scorer with large inputs."""
    query = "What is the story about?"
    context, output = generate_context_and_output(100_000, context_ratio=0.8)

    result = await context_relevance_scorer.score(
        query=query,
        context=context,
        output=output,
        verbose=True
    )

    assert "flagged" in result
    assert "extras" in result
    assert "score" in result["extras"]
    assert "all_spans" in result["extras"]


@pytest.mark.asyncio
async def test_context_relevance_scorer_error_handling(context_relevance_scorer):
    """Test error handling in the context relevance scorer."""
    with pytest.raises(ValueError):
        await context_relevance_scorer.score(
            query="",
            context="",
            output="",
            verbose=True
        )
