import pytest

from tests.scorers.test_utils import TINY_MODEL_PATHS, generate_large_text
from weave.scorers.moderation_scorer import WeaveBiasScorer


@pytest.fixture
def weave_bias_scorer():
    """Fixture that returns a WeaveBiasScorer instance using a tiny downloaded model."""
    return WeaveBiasScorer(
        model_name_or_path=TINY_MODEL_PATHS["bias_scorer"],
        device="cpu",  # Use CPU for testing
        threshold=0.5,
    )


def test_bias_scorer_simple(weave_bias_scorer):
    """Tests that the scorer can handle a basic string."""
    output = "This is a balanced statement with no bias."
    result = weave_bias_scorer.score(output)
    assert not result.passed


def test_bias_scorer_large_input(weave_bias_scorer):
    """Tests bias scorer with very large input to ensure it doesn't crash."""
    large_text = generate_large_text(100_000)  # 100k characters
    _ = weave_bias_scorer.score(large_text)


def test_bias_scorer_threshold(weave_bias_scorer):
    """
    Confirms that the threshold logic works properly.
    This example text is contrived to produce mild results in categories.
    """
    text = "This text slightly contains gender bias and maybe a hint of racial bias."
    result = weave_bias_scorer.score(text)

    # The scorer's logic sets:
    #   scores = [o >= self.threshold for o in predictions]
    #   passed = not any(scores)
    # Thus, if any category has a score above the threshold, overall passed should be False.
    flags = [
        result.extras[category.lower()] for category in weave_bias_scorer._categories
    ]
    should_pass = not any(flags)
    assert result.passed == should_pass, "Threshold logic did not work as expected."
