import pytest
import math

import weave
from weave.scorers.robustness_scorer import RobustnessScorer


def truncate(number, decimals=0):
    """
    Truncates a number to the specified number of decimal places without rounding.
    """
    factor = 10.0 ** decimals
    return math.trunc(number * factor) / factor


def test_robustness_scorer():
    # Example output with original and perturbed generations
    output = ["True", "False", "True", "True", "False"]

    # Instantiate the scorer
    robustness_scorer = RobustnessScorer()

    # Run the scorer's `score` method
    result = robustness_scorer.score(output=output)

    # Assert that the result matches the expected Cohen's h value
    assert truncate(result["cohen_h"], 5) == 0.49999


def test_robustness_scorer_perfect_similarity():
    output = ["True", "True", "True", "True"]
    robustness_scorer = RobustnessScorer()
    result = robustness_scorer.score(output=output)
    assert result["cohen_h"] == 0.0


def test_robustness_scorer_no_similarity():
    output = ["True", "False", "False", "False", "False"]
    robustness_scorer = RobustnessScorer()
    result = robustness_scorer.score(output=output)
    assert result["cohen_h"] == 1.0


def test_robustness_scorer_single_perturbation():
    output = ["True", "False"]
    robustness_scorer = RobustnessScorer()
    result = robustness_scorer.score(output=output)
    assert result["cohen_h"] == 1.0


def test_robustness_scorer_insufficient_outputs():
    output = ["True"]  # No perturbed outputs
    robustness_scorer = RobustnessScorer()
    with pytest.raises(
        AssertionError, match="There must be output of at least one perturbed question"
    ):
        robustness_scorer.score(output=output)
