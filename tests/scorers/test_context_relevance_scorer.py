"""Tests for the Context Relevance Scorer."""

import pytest

from weave.scorers.context_relevance_scorer import WeaveContextRelevanceScorerV1
from weave.scorers.default_models import MODEL_PATHS


@pytest.fixture
def weave_context_relevance_scorer():
    """Fixture that returns a WeaveContextRelevanceScorerV1 instance,
    referencing the 'relevance_scorer' checkpoint.
    """
    scorer = WeaveContextRelevanceScorerV1(
        model_name_or_path=MODEL_PATHS["relevance_scorer"],
        device="cpu",  # Use CPU for testing
    )

    return scorer


def test_context_relevance_scorer_basic(weave_context_relevance_scorer):
    """Test that a basic matching query/output does not get flagged."""
    query = "What is the moon made of?"
    output = (
        "The moon is a big rock made primarily of silicate minerals. It consists of an \
iron-rich core, a rocky mantle, and a thin crust composed mainly of oxygen, silicon, magnesium, \
iron, calcium, and aluminum."
    )
    result = weave_context_relevance_scorer.score(
        query=query,
        output=output,
    )
    # With full models, relevant context should pass
    assert result.passed
    assert result.metadata["score"] > 0.5


def test_long_context(weave_context_relevance_scorer):
    """Test the context relevance scorer with a long context."""
    query = "What is the capital of France?"
    # Generate a context about something completely unrelated
    irrelevant_context = (
        "The process of photosynthesis involves chlorophyll capturing light energy. "
        * 1000
    )
    irrelevant_context += "Mitochondria are the powerhouses of the cell. " * 1000
    irrelevant_context += (
        "DNA replication occurs during the S phase of the cell cycle. " * 1000
    )

    result = weave_context_relevance_scorer.score(
        query=query,
        output=irrelevant_context,
    )
    # Long irrelevant context about biology should not be relevant to a geography question
    assert not result.passed
    assert result.metadata["score"] < 0.55
