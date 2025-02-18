"""Tests for the Context Relevance Scorer."""

import pytest

from tests.scorers.test_utils import TINY_MODEL_PATHS, generate_context_and_output
from weave.scorers.context_relevance_scorer import WeaveContextRelevanceScorerV1


@pytest.fixture
def weave_context_relevance_scorer():
    """
    Fixture that returns a WeaveContextRelevanceScorerV1 instance,
    referencing the 'relevance_scorer' checkpoint.
    """
    scorer = WeaveContextRelevanceScorerV1(
        model_name_or_path=TINY_MODEL_PATHS["relevance_scorer"],
        device="cpu",  # Use CPU for testing
    )

    return scorer


def test_context_relevance_scorer_basic(weave_context_relevance_scorer):
    """Test that a basic matching query/output does not get flagged."""
    query = "The moon is a big rock."
    output = "The moon is a big rock."
    result = weave_context_relevance_scorer.score(
        query=query,
        output=output,
    )
    # Using attributes from the pydantic model
    assert not result.passed
    assert result.metadata["score"] > 0


def test_long_context(weave_context_relevance_scorer):
    """Test the context relevance scorer with a long context."""
    query = "The moon is a big rock."
    output, _ = generate_context_and_output(total_tokens=100_000)
    result = weave_context_relevance_scorer.score(
        query=query,
        output=output,
    )
    assert not result.passed
    assert result.metadata["score"] < 1.0
