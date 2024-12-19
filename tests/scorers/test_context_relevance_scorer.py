"""Tests for the Context Relevance Scorer."""

import pytest

from tests.scorers.test_utils import TINY_MODEL_PATHS, generate_context_and_output
from weave.scorers.context_relevance_scorer import ContextRelevanceScorer
from weave.scorers.llm_utils import download_model


@pytest.fixture
def context_relevance_scorer():
    """Fixture that returns a ContextRelevanceScorer instance."""
    tiny_model_path = download_model(TINY_MODEL_PATHS["relevance_scorer"])
    scorer = ContextRelevanceScorer(
        model_name_or_path=tiny_model_path,
    )
    return scorer


def test_context_relevance_scorer(context_relevance_scorer):
    """Test the context relevance scorer."""
    query = "The moon is a big rock."
    output = "The moon is a big rock."
    context = "The moon is a big rock."

    result = context_relevance_scorer.score(
        query=query,
        output=output,
        context=context,
    )

    assert result["flagged"] == False
    assert result["extras"]["score"] == 0.0

    result = context_relevance_scorer.score(
        query=query,
        output=output,
        context=context,
        verbose=True,
    )

    assert result["flagged"] == False
    assert result["extras"]["score"] == 0.0
    assert "all_spans" in result["extras"]


def test_long_context(context_relevance_scorer):
    """Test the context relevance scorer with a long context."""
    context, output = generate_context_and_output(total_tokens=100_000)
    result = context_relevance_scorer.score(
        query="The moon is a big rock.",
        output=output,
        context=context,
    )

    assert result["flagged"] == False
    assert result["extras"]["score"] == 0.0
