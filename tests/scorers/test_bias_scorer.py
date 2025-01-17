import pytest

from tests.scorers.test_utils import TINY_MODEL_PATHS, generate_large_text
from weave.scorers.llm_utils import download_model
from weave.scorers.moderation_scorer import BiasScorer


@pytest.fixture
def bias_scorer():
    """Fixture that returns a BiasScorer instance using a tiny downloaded model."""
    tiny_model_path = download_model(TINY_MODEL_PATHS["bias_scorer"])
    return BiasScorer(
        model_name_or_path=tiny_model_path,
        name="test-bias",
        description="Tiny test bias scorer",
        device="cpu",  # Use CPU for testing
        threshold=0.5,
    )


def test_bias_scorer_simple(bias_scorer):
    """Tests that the scorer can handle a basic string."""
    output = "This is a balanced statement with no bias."
    result = bias_scorer.score(output)

    assert isinstance(result, dict), "Result should be a dictionary."
    assert "flagged" in result, "Result must contain the 'flagged' key."
    assert "extras" in result, "Result must contain the 'extras' dictionary."
    assert isinstance(result["flagged"], bool), "'flagged' must be a boolean."
    assert isinstance(result["extras"], dict), "'extras' must be a dictionary."
    for category in bias_scorer._categories:
        assert (
            category in result["extras"]
        ), f"'{category}' should be in 'extras' dictionary."


def test_bias_scorer_large_input(bias_scorer):
    """Tests bias scorer with very large input to ensure it doesn't crash."""
    large_text = generate_large_text(100_000)  # 100k characters
    result = bias_scorer.score(large_text)

    assert isinstance(result, dict)
    assert "flagged" in result
    assert isinstance(result["flagged"], bool)
    assert "extras" in result
    for category in bias_scorer._categories:
        assert category in result["extras"], f"'{category}' should be in 'extras'."


def test_bias_scorer_threshold(bias_scorer):
    """
    Confirms that the threshold logic works properly.
    This example text is contrived to produce mild results in categories.
    """
    text = "This text slightly contains gender bias and maybe a hint of racial bias."
    result = bias_scorer.score(text)

    assert isinstance(result, dict), "Result should be a dictionary."
    assert "flagged" in result, "Should have a 'flagged' key in result."
    assert isinstance(result["flagged"], bool), "'flagged' must be a boolean."
    scores = result["extras"]
    # If any score is above threshold, it should be flagged
    should_flag = any(v is True for v in scores.values())
    assert result["flagged"] == should_flag
