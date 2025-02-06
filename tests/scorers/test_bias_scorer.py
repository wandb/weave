import pytest

from tests.scorers.test_utils import TINY_MODEL_PATHS, generate_large_text
from weave.scorers.llm_utils import download_model
from weave.scorers.moderation_scorer import WeaveBiasScorer


@pytest.fixture
def weave_bias_scorer():
    """Fixture that returns a WeaveBiasScorer instance using a tiny downloaded model."""
    tiny_model_path = download_model(TINY_MODEL_PATHS["bias_scorer"])
    return WeaveBiasScorer(
        model_name_or_path=tiny_model_path,
        name="test-bias",
        description="Tiny test bias scorer",
        device="cpu",  # Use CPU for testing
        threshold=0.5,
    )


def test_bias_scorer_simple(weave_bias_scorer):
    """Tests that the scorer can handle a basic string."""
    output = "This is a balanced statement with no bias."
    result = weave_bias_scorer.score(output)

    assert isinstance(result, dict), "Result should be a dictionary."
    assert "pass" in result, "Result must contain the 'pass' key."
    assert "extras" in result, "Result must contain the 'extras' dictionary."
    assert isinstance(result["pass"], bool), "'pass' must be a boolean."
    assert isinstance(result["extras"], dict), "'extras' must be a dictionary."
    for category in weave_bias_scorer._categories:
        assert (
            category in result["extras"]
        ), f"'{category}' should be in 'extras' dictionary."


def test_bias_scorer_large_input(weave_bias_scorer):
    """Tests bias scorer with very large input to ensure it doesn't crash."""
    large_text = generate_large_text(100_000)  # 100k characters
    result = weave_bias_scorer.score(large_text)

    assert isinstance(result, dict)
    assert "pass" in result
    assert isinstance(result["pass"], bool)
    assert "extras" in result
    for category in weave_bias_scorer._categories:
        assert category in result["extras"], f"'{category}' should be in 'extras'."


def test_bias_scorer_threshold(weave_bias_scorer):
    """
    Confirms that the threshold logic works properly.
    This example text is contrived to produce mild results in categories.
    """
    text = "This text slightly contains gender bias and maybe a hint of racial bias."
    result = weave_bias_scorer.score(text)

    assert isinstance(result, dict), "Result should be a dictionary."
    assert "pass" in result, "Should have a 'pass' key in result."
    assert isinstance(result["pass"], bool), "'pass' must be a boolean."
    scores = result["extras"]
    # If any score is above threshold, it should not pass
    should_pass = not any(v is True for v in scores.values())
    assert result["pass"] == should_pass
