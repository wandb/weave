"""Tests for the Context Relevance Scorer."""
import pytest
from weave.scorers.context_relevance_scorer import ContextRelevanceScorer
from tests.scorers.test_utils import generate_large_text, generate_context_and_output


@pytest.fixture
def context_relevance_scorer():
    """Create a context relevance scorer for testing."""
    return ContextRelevanceScorer()


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
