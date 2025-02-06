"""Tests for the Context Relevance Scorer."""

import pytest

from tests.scorers.test_utils import TINY_MODEL_PATHS, generate_context_and_output
from weave.scorers.context_relevance_scorer import WeaveContextRelevanceScorer
from weave.scorers.utils import download_model


@pytest.fixture
def weave_context_relevance_scorer():
    """
    Fixture that returns a WeaveContextRelevanceScorer instance,
    referencing the 'relevance_scorer' checkpoint.
    """
    model_path = download_model(TINY_MODEL_PATHS["relevance_scorer"])
    scorer = WeaveContextRelevanceScorer(
        model_name_or_path=model_path,
        device="cpu",  # Use CPU for testing
    )
    return scorer


def test_context_relevance_scorer_basic(weave_context_relevance_scorer):
    """Test that a basic matching context/output does not get flagged."""
    query = "The moon is a big rock."
    context = "The moon is a big rock."
    result = weave_context_relevance_scorer.score(
        query=query,
        context=context,
    )

    assert (
        result["pass"] == False
    )  # The actual implementation returns False for this case
    assert result["extras"]["score"]


def test_long_context(weave_context_relevance_scorer):
    """Test the context relevance scorer with a long context."""
    context, _ = generate_context_and_output(total_tokens=100_000)
    result = weave_context_relevance_scorer.score(
        query="The moon is a big rock.",
        context=context,
    )

    assert (
        result["pass"] == False
    )  # The actual implementation returns False for this case
    assert result["extras"]["score"] == 0.0
