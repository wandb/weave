import pytest

from tests.scorers.test_utils import TINY_MODEL_PATHS, generate_context_and_output
from weave.scorers import HallucinationScorer
from weave.scorers.llm_utils import download_model


@pytest.fixture
def hallucination_scorer():
    """
    Fixture that returns a HallucinationScorer instance,
    referencing the 'hallucination_hhem_scorer' checkpoint.
    """
    model_path = download_model(TINY_MODEL_PATHS["hallucination_hhem_scorer"])
    scorer = HallucinationScorer(
        model_name_or_path=model_path,
        use_hhem=True,
    )
    return scorer


def test_hallucination_scorer_basic(hallucination_scorer):
    """
    Test that a basic matching context/output does not get flagged.
    """
    query = "The moon is a big rock."
    context = "The moon is a big rock."
    output = "The moon is a big rock."
    result = hallucination_scorer.score(query=query, context=context, output=output)

    assert isinstance(result, dict), "Result should be a dictionary"
    assert "flagged" in result, "Result should contain 'flagged' key"
    assert "extras" in result, "Result should contain 'extras' key"
    assert result["flagged"] is False, "Matching context/output should not be flagged"
    assert "score" in result["extras"], "Result extras should contain a 'score' field"


def test_hallucination_scorer_long_input(hallucination_scorer):
    """
    Test that the scorer can handle a longer context/output without errors.
    """
    query = "What is the text about?"
    context, output = generate_context_and_output(
        total_tokens=5000  # moderately large for a test
    )
    result = hallucination_scorer.score(query=query, context=context, output=output)

    # We only check that the result structure is valid;
    # the actual flagged/score value depends on how the model scores the content.
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "flagged" in result, "Result should contain 'flagged' key"
    assert "extras" in result, "Result should contain 'extras' key"
    assert "score" in result["extras"], "Result extras should contain a 'score' field"
