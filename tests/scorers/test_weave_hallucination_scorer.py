import pytest

from tests.scorers.test_utils import TINY_MODEL_PATHS, generate_large_text
from weave.scorers.hallucination_scorer import WeaveHallucinationScorerV1


@pytest.fixture
def weave_hallucination_scorer():
    """Fixture that returns a WeaveHallucinationScorerV1 instance using a tiny downloaded model."""
    return WeaveHallucinationScorerV1(
        model_name_or_path=TINY_MODEL_PATHS["hallucination_hhem_scorer"],
        device="cpu",  # Use CPU for testing
        threshold=0.35,  # Default threshold from the class
    )


def test_weave_hallucination_scorer_simple(weave_hallucination_scorer):
    """Tests that the scorer can handle a basic string."""
    query = "What is the capital of France?"
    context = "Paris is the capital of France."
    output = "Paris is the capital of France."
    result = weave_hallucination_scorer.score(query=query, context=context, output=output)
    assert result.passed  # Should pass since output matches context exactly


def test_weave_hallucination_scorer_large_input(weave_hallucination_scorer):
    """Tests hallucination scorer with very large input to ensure it doesn't crash."""
    query = "Summarize this text."
    large_context_text = generate_large_text(100_000)  # 100k characters
    output = "This is a very long text."
    _ = weave_hallucination_scorer.score(query=query, context=large_context_text, output=output)


def test_weave_hallucination_scorer_threshold(weave_hallucination_scorer):
    """
    Confirms that the threshold logic works properly.
    This example text is contrived to produce a hallucination.
    """
    query = "What is John's favorite food?"
    context = "John likes various types of food."
    output = "Monkeys play pianos on the moon."  # This is a hallucination since it's not supported by query or context
    result = weave_hallucination_scorer.score(query=query, context=context, output=output)

    # The scorer's logic sets:
    #   passed = score <= threshold
    # Thus, if the score is above the threshold, overall passed should be False
    score = result.extras["score"]
    should_pass = score <= weave_hallucination_scorer.threshold
    assert result.passed == should_pass, "Threshold logic did not work as expected."