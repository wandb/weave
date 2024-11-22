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
    ground_truths = [
        False,
        False,
        False,
        False,
    ]  # Booleans will be converted to strings
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


def test_robustness_scorer_non_binary():
    # Example outputs with original and perturbed sentences
    output = [
        "The quick brown fox jumps over the lazy dog.",
        "A fast dark fox leaps over a sleepy canine.",
        "The quick brown fox hops over the lazy dog.",
        "An agile red fox jumps over the lazy hound."
    ]

    # Instantiate the scorer with binary=False
    robustness_scorer = RobustnessScorer(binary=False)

    # Run the scorer's `score` method
    result = robustness_scorer.score(output=output)

    print(result)

    # Assert that the result contains 'cohen_d' and is a float
    assert 'cohen_d' in result
    assert isinstance(result['cohen_d'], float)

    # Check that the effect size is within a reasonable range
    assert 0 <= abs(result['cohen_d']) <= 3, f"Cohen's d is out of expected range: {result['cohen_d']}"


def test_robustness_scorer_non_binary_with_ground_truths():
    # Outputs from the model
    output = [
        "The capital of France is Paris.",
        "Paris is the capital city of France.",
        "France's capital is Paris.",
        "The capital city of France is Paris."
    ]

    # Ground truths corresponding to each output
    ground_truths = [
        "Paris",
        "Paris",
        "Paris",
        "Paris"
    ]

    # Instantiate the scorer with binary=False
    robustness_scorer = RobustnessScorer(binary=False)

    # Run the scorer's `score` method
    result = robustness_scorer.score(output=output, ground_truths=ground_truths)

    print(result)

    # Assert that the result contains 'cohen_d' and is a float
    assert 'cohen_d' in result
    assert isinstance(result['cohen_d'], float)

    # Check that the effect size is within a reasonable range
    assert 0 <= abs(result['cohen_d']) <= 3, f"Cohen's d is out of expected range: {result['cohen_d']}"


def test_robustness_scorer_invalid_similarity_metric():
    output = ["Text A", "Text B"]
    robustness_scorer = RobustnessScorer(binary=False, similarity_metric="invalid_metric")

    with pytest.raises(ValueError, match="Unsupported similarity metric: invalid_metric"):
        robustness_scorer.score(output=output)


def test_robustness_scorer_zero_variance():
    output = [
        "The quick brown fox jumps over the lazy dog.",
        "The quick brown fox jumps over the lazy dog.",
        "The quick brown fox jumps over the lazy dog.",
        "The quick brown fox jumps over the lazy dog."
    ]

    robustness_scorer = RobustnessScorer(binary=False)
    result = robustness_scorer.score(output=output)

    # Since all outputs are identical, differences are zero, and std_dev is zero
    assert result['cohen_d'] == 0.0


def test_robustness_scorer_long_texts():
    output = [
        "In a village of La Mancha, the name of which I have no desire to call to mind, "
        "there lived not long since one of those gentlemen that keep a lance in the lance-rack, "
        "an old buckler, a lean hack, and a greyhound for coursing.",
        "In a small town in La Mancha, whose name I don't care to remember, there lived not long ago "
        "one of those gentlemen who always have a lance and ancient shield on a shelf, "
        "a skinny nag, and a greyhound for hunting.",
        "In a certain village in La Mancha, which I shall not name, there lived recently a gentleman "
        "who kept a spear in his rack, an old shield, a thin horse, and a hunting greyhound."
    ]

    robustness_scorer = RobustnessScorer(binary=False)
    result = robustness_scorer.score(output=output)

    # Assert that the scorer returns a valid effect size
    assert 'cohen_d' in result
    assert isinstance(result['cohen_d'], float)


def test_robustness_scorer_unicode_texts():
    output = [
        "C'est la vie 😊",  # Original output with emoji
        "C'est la vie 😊",  # Identical perturbed output
        "C'est la vie 😢",  # Perturbed output with different emoji
        "C'est la vie"      # Perturbed output without emoji
    ]

    robustness_scorer = RobustnessScorer(binary=False)
    result = robustness_scorer.score(output=output)

    # Assert that the scorer computes a valid effect size
    assert 'cohen_d' in result
    assert isinstance(result['cohen_d'], float)


def test_robustness_scorer_unicode_texts():
    output = [
        "C'est la vie 😊",  # Original output with emoji
        "C'est la vie 😊",  # Identical perturbed output
        "C'est la vie 😢",  # Perturbed output with different emoji
        "C'est la vie"      # Perturbed output without emoji
    ]

    robustness_scorer = RobustnessScorer(binary=False)
    result = robustness_scorer.score(output=output)

    # Assert that the scorer computes a valid effect size
    assert 'cohen_d' in result
    assert isinstance(result['cohen_d'], float)


def test_robustness_scorer_compute_similarity_exception():
    output = ["Text A", "Text B"]
    robustness_scorer = RobustnessScorer(binary=False)

    # Mock the embedding model to raise an exception
    def mock_encode(*args, **kwargs):
        raise RuntimeError("Mocked exception in embedding model.")

    robustness_scorer.embedding_model.encode = mock_encode

    with pytest.raises(RuntimeError, match="Mocked exception in embedding model."):
        robustness_scorer.score(output=output)


def test_robustness_scorer_mixed_data_types():
    output = ["42", 42, True, None]

    robustness_scorer = RobustnessScorer()

    # Since outputs are converted to strings, this should work
    result = robustness_scorer.score(output=output)

    # Assert that the scorer computes a valid effect size
    assert 'cohen_h' in result
    assert isinstance(result['cohen_h'], float)


def test_robustness_scorer_multilingual_texts():
    output = [
        "Hello, how are you?",          # English
        "Hola, ¿cómo estás?",           # Spanish
        "Bonjour, comment ça va?",      # French
        "こんにちは、お元気ですか？",    # Japanese
    ]

    robustness_scorer = RobustnessScorer(binary=False)
    result = robustness_scorer.score(output=output)

    # Since texts are in different languages, expect low similarities
    assert result['score(perturbed)'] < 0.5


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
            "ground_truths": [
                "Elon Musk",
                "Elon Musk",
                "Elon Musk",
            ],  # Ground truths as strings
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


import pytest
import weave
from weave.scorers.robustness_scorer import RobustnessScorer

@pytest.mark.asyncio
async def test_robustness_scorer_non_binary_evaluation():
    # Simulated dataset with questions (original and perturbed)
    dataset = [
        {
            "questions": [
                "What is the capital of France?",     # Original question
                "What's the capital of France?",      # Perturbed question 1
                "What is France's capital city?",     # Perturbed question 2
            ],
        },
        {
            "questions": [
                "Who is the CEO of Apple?",           # Original question
                "Who leads Apple Inc.?",              # Perturbed question 1
                "Name the chief executive of Apple.", # Perturbed question 2
            ],
        },
    ]

    @weave.op
    def model(questions: list[str]):
        # Simulated model outputs corresponding to each question
        outputs = [
            "The capital of France is Paris.",
            "Paris is the capital of France.",
            "France's capital is Berlin.",
        ]
        return outputs

    # Instantiate the RobustnessScorer with binary=False
    robustness_scorer = RobustnessScorer(binary=False)

    # Perform evaluation using Weave's Evaluation framework
    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[robustness_scorer],
    )

    # Run the evaluation
    result = await evaluation.evaluate(model)

    print(result)

    # Print the results
    print("Robustness Scorer Results:")
    print(result["RobustnessScorer"])

    # Assert that the 'cohen_d' is present and is a float
    assert "cohen_d" in result["RobustnessScorer"]
    assert isinstance(result["RobustnessScorer"]["cohen_d"]["mean"], float)

    # Optionally, you can check that the effect size is within a reasonable range
    cohen_d_mean = result["RobustnessScorer"]["cohen_d"]["mean"]
    assert 0 <= abs(cohen_d_mean) <= 3, f"Cohen's d mean is out of expected range: {cohen_d_mean}"