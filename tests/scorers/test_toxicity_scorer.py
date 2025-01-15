import pytest

from tests.scorers.test_utils import TINY_MODEL_PATHS, generate_large_text
from weave.scorers.llm_utils import download_model
from weave.scorers.moderation_scorer import ToxicityScorer


@pytest.fixture
def toxicity_scorer():
    """
    Fixture that returns a ToxicityScorer instance using a tiny downloaded model,
    similar to test_context_relevance_scorer.py logic.
    """
    tiny_model_path = download_model(TINY_MODEL_PATHS["toxicity_scorer"])
    return ToxicityScorer(
        model_name_or_path=tiny_model_path,
        name="test-toxicity",
        description="Tiny test toxicity scorer",
        device="cpu",  # Use CPU for testing
        total_threshold=5,
        category_threshold=2,
    )


def test_toxicity_scorer_simple(toxicity_scorer):
    """Tests that the scorer can handle a basic string."""
    output = "Just a simple, harmless sentence."
    result = toxicity_scorer.score(output)

    assert isinstance(result, dict), "Result should be a dictionary."
    assert "flagged" in result, "Result must contain the 'flagged' key."
    assert "extras" in result, "Result must contain the 'extras' dictionary."
    assert isinstance(result["flagged"], bool), "'flagged' must be a boolean."
    assert isinstance(result["extras"], dict), "'extras' must be a dictionary."
    for category in toxicity_scorer._categories:
        assert (
            category in result["extras"]
        ), f"'{category}' should be in 'extras' dictionary."


def test_toxicity_scorer_large_input(toxicity_scorer):
    """Tests toxicity scorer with very large input to ensure it doesn't crash."""
    large_text = generate_large_text(100_000)  # 100k characters
    result = toxicity_scorer.score(large_text)

    assert isinstance(result, dict)
    assert "flagged" in result
    assert isinstance(result["flagged"], bool)
    assert "extras" in result
    assert all(cat in result["extras"] for cat in toxicity_scorer._categories)


def test_toxicity_scorer_threshold(toxicity_scorer):
    """
    Confirms that the total threshold logic and category threshold logic both work.
    This example text is contrived to produce mild results in multiple categories.
    """
    text = "This text slightly offends many groups just a little bit."
    result = toxicity_scorer.score(text)

    assert isinstance(result, dict)
    assert "flagged" in result
    assert isinstance(result["flagged"], bool)
    assert "extras" in result
    total_score = sum(result["extras"].values())
    highest_cat_score = max(result["extras"].values())
    should_flag = (total_score >= toxicity_scorer.total_threshold) or (
        highest_cat_score >= toxicity_scorer.category_threshold
    )
    assert result["flagged"] == should_flag


# def test_toxicity_scorer_clean(toxicity_scorer):
#     """
#     Tests behavior on benign content that should not trigger any category flags.
#     """
#     clean_text = "I really enjoy friendly and respectful conversations."
#     result = toxicity_scorer.score(clean_text)

#     assert isinstance(result, dict)
#     assert "extras" in result
#     assert all(cat in result["extras"] for cat in toxicity_scorer._categories)
#     assert not result["flagged"], "Clean text should not be flagged."
