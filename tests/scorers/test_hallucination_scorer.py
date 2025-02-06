import pytest

from tests.scorers.test_utils import TINY_MODEL_PATHS, generate_context_and_output
from weave.scorers import WeaveHallucinationScorer
from weave.scorers.llm_utils import download_model


@pytest.fixture
def weave_hallucination_scorer():
    """
    Fixture that returns a WeaveHallucinationScorer instance,
    referencing the 'hallucination_hhem_scorer' checkpoint.
    """
    model_path = download_model(TINY_MODEL_PATHS["hallucination_hhem_scorer"])
    scorer = WeaveHallucinationScorer(
        model_name_or_path=model_path,
        use_hhem=True,
        device="cpu",
        threshold=0.35,
    )
    return scorer


def test_weave_hallucination_scorer_basic(weave_hallucination_scorer):
    """Test that a basic matching context/output does not get flagged."""
    query = "The moon is a big rock."
    context = "The moon is a big rock."
    output = "The moon is a big rock."
    result = weave_hallucination_scorer.score(query=query, context=context, output=output)

    assert isinstance(result, dict), "Result should be a dictionary"
    assert "pass" in result, "Result should contain 'pass' key"
    assert "extras" in result, "Result should contain 'extras' key"
    assert result["pass"] is True, "Matching context/output should not be flagged"
    assert "score" in result["extras"], "Result extras should contain a 'score' field"


def test_weave_hallucination_scorer_long_input(weave_hallucination_scorer):
    """Test that the scorer can handle a longer context/output without errors."""
    query = "What is the text about?"
    context, output = generate_context_and_output(
        total_tokens=5000  # moderately large for a test
    )
    result = weave_hallucination_scorer.score(query=query, context=context, output=output)

    # We only check that the result structure is valid;
    # the actual flagged/score value depends on how the model scores the content.
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "pass" in result, "Result should contain 'pass' key"
    assert "extras" in result, "Result should contain 'extras' key"
    assert "score" in result["extras"], "Result extras should contain a 'score' field"
