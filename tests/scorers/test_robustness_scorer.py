import math

import pytest

import weave
from weave.scorers.robustness_scorer import RobustnessScorer


def truncate(number, decimals=0):
    """Truncates a number to the specified number of decimal places without rounding."""
    factor = 10.0**decimals
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


def test_robustness_scorer_with_boolean_output():
    output = [True, True, False, True]  # Boolean outputs from the system
    robustness_scorer = RobustnessScorer()
    result = robustness_scorer.score(output=output)
    assert truncate(result["cohen_h"], 5) == 0.39182


def test_robustness_scorer_with_boolean_output_and_ground_truths():
    output = [True, True, False, True]  # Boolean outputs from the system
    ground_truths = [True, True, True, True]  # Boolean ground truths
    robustness_scorer = RobustnessScorer()
    result = robustness_scorer.score(output=output, ground_truths=ground_truths)
    assert truncate(result["cohen_h"], 5) == 0.39182


def test_robustness_scorer_with_ground_truths_as_strings():
    output = ["apple", "aple", "orange", "apple"]
    ground_truths = ["apple", "apple", "apple", "apple"]
    robustness_scorer = RobustnessScorer()
    result = robustness_scorer.score(output=output, ground_truths=ground_truths)
    assert truncate(result["cohen_h"], 5) == 0.60817


def test_robustness_scorer_with_ground_truths_as_booleans():
    output = ["True", "True", "False", "True"]
    ground_truths = [False, False, False, False]  # Booleans will be converted to strings
    robustness_scorer = RobustnessScorer()
    result = robustness_scorer.score(output=output, ground_truths=ground_truths)
    assert truncate(result["cohen_h"], 5) == 0.39182


def test_robustness_scorer_ground_truths_length_mismatch():
    output = ["True", "False", "True"]
    ground_truths = ["True", "True"]  # Mismatched length
    robustness_scorer = RobustnessScorer()
    with pytest.raises(
        AssertionError, match="Length of ground_truths must match the length of output."
    ):
        robustness_scorer.score(output=output, ground_truths=ground_truths)


def test_robustness_scorer_ground_truths_edge_case():
    output = ["True"]
    ground_truths = ["True"]
    robustness_scorer = RobustnessScorer()
    with pytest.raises(
        AssertionError, match="There must be output of at least one perturbed question."
    ):
        robustness_scorer.score(output=output, ground_truths=ground_truths)


@pytest.mark.asyncio
async def test_robustness_scorer_eval():
    dataset = [
        {
            "questions": [
                "What is the capital of France?",
                "what the capital of france?",
                "Wht is the Capital of France?",
            ],
        },
        {
            "questions": [
                "Who is the owner of X.com?",
                "who is the owner of x.com?",
                "Who owns X.com?",
            ],
        },
    ]

    @weave.op
    def model(questions: list[str]):
        perturbed_outputs = [False, True]
        return ["True"] + perturbed_outputs

    robustness_scorer = RobustnessScorer()

    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[robustness_scorer],
    )
    result = await evaluation.evaluate(model)
    assert truncate(result["RobustnessScorer"]["cohen_h"]["mean"], 5) == 0.49999


@pytest.mark.asyncio
async def test_robustness_scorer_eval_with_ground_truths():
    # Simulated dataset with questions and corresponding ground truths
    dataset = [
        {
            "questions": [
                "What is the capital of France?",
                "what is the capital of france?",
                "What is the Capital of france?",
            ],
            "ground_truths": ["Paris", "Paris", "Paris"],  # Ground truths as strings
        },
        {
            "questions": [
                "Who is the owner of X.com?",
                "who owns x.com?",
                "Who is the current owner of X.com?",
            ],
            "ground_truths": ["Elon Musk", "Elon Musk", "Elon Musk"],  # Ground truths as strings
        },
    ]

    # Simulated LLM model output, matching the dataset structure
    @weave.op
    def model(questions: list[str]):
        outputs = [
            "Paris",
            "Paris",
            "Lyon",
        ]
        return outputs

    # Instantiate the RobustnessScorer
    robustness_scorer = RobustnessScorer()

    # Perform evaluation using Weave's Evaluation framework
    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[robustness_scorer],
    )
    result = await evaluation.evaluate(model)

    # Check that Cohen's h is computed as expected
    assert "RobustnessScorer" in result, "Scorer results are missing."
    cohen_h_mean = truncate(result["RobustnessScorer"]["cohen_h"]["mean"], 5)
    assert cohen_h_mean == 0.24999, f"Unexpected Cohen's h mean: {cohen_h_mean}"
