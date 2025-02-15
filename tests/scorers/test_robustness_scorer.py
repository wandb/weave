import math
import string

import pytest  # type: ignore

import weave
from weave.scorers import WeaveRobustnessScorer
from weave.scorers.robustness_scorer import (
    add_whitespace,
    butterfingers,
    create_perturbed_dataset,
    emphasize_words,
    random_capitalization,
    random_case_change,
    remove_punctuation,
    split_merge_words,
    swap_chars,
    text_noise,
)


def truncate(number, decimals=0):
    """Truncates a number to the specified number of decimal places without rounding."""
    factor = 10.0**decimals
    return math.trunc(number * factor) / factor


def test_robustness_scorer():
    # Example output with original and perturbed generations
    reference_text = "True"
    texts = ["False", "True", "True", "False"]

    # Instantiate the scorer
    robustness_scorer = WeaveRobustnessScorer(
        use_exact_match=True,
        device="cpu",
        model_name_or_path="",  # Will use default model
    )

    # Run the scorer's `score` method
    result = robustness_scorer.score(reference_text=reference_text, texts=texts)

    # Assert that the result matches the expected Cohen's h value
    assert truncate(result["cohen_h"], 5) == 0.49999


def test_robustness_scorer_perfect_similarity():
    reference_text = "True"
    texts = ["True", "True", "True"]
    robustness_scorer = WeaveRobustnessScorer(
        use_exact_match=True,
        device="cpu",
        model_name_or_path="",
    )
    result = robustness_scorer.score(reference_text=reference_text, texts=texts)
    assert result["cohen_h"] == 0.0


def test_robustness_scorer_no_similarity():
    reference_text = "True"
    texts = ["False", "False", "False", "False"]
    robustness_scorer = WeaveRobustnessScorer(
        use_exact_match=True,
        device="cpu",
        model_name_or_path="",
    )
    result = robustness_scorer.score(reference_text=reference_text, texts=texts)
    assert result["cohen_h"] == 1.0


def test_robustness_scorer_single_perturbation():
    reference_text = "True"
    texts = ["False"]
    robustness_scorer = WeaveRobustnessScorer(
        use_exact_match=True,
        device="cpu",
        model_name_or_path="",
    )
    result = robustness_scorer.score(reference_text=reference_text, texts=texts)
    assert result["cohen_h"] == 1.0


def test_robustness_scorer_insufficient_outputs():
    reference_text = "True"
    texts = []  # No perturbed outputs
    robustness_scorer = WeaveRobustnessScorer()
    with pytest.raises(
        AssertionError,
        match="There are no `texts`, there must be at least one text to measure against.",
    ):
        robustness_scorer.score(reference_text=reference_text, texts=texts)


def test_robustness_scorer_with_boolean_output():
    reference_text = True
    texts = [True, False, True]  # Boolean outputs from the system
    robustness_scorer = WeaveRobustnessScorer(
        use_exact_match=True,
        device="cpu",
        model_name_or_path="",
    )
    result = robustness_scorer.score(reference_text=reference_text, texts=texts)
    assert truncate(result["cohen_h"], 5) == 0.39182


def test_robustness_scorer_with_boolean_output_and_ground_truths():
    reference_text = True
    texts = [True, False, True]  # Boolean outputs from the system
    ground_truths = [True, True, True]  # Boolean ground truths
    robustness_scorer = WeaveRobustnessScorer(
        use_exact_match=True,
        device="cpu",
        model_name_or_path="",
        use_ground_truths=True,
    )
    result = robustness_scorer.score(
        reference_text=reference_text, texts=texts, ground_truths=ground_truths
    )
    assert truncate(result["cohen_h"], 5) == 0.39182


def test_robustness_scorer_with_ground_truths_as_strings():
    reference_text = "apple"
    texts = ["aple", "orange", "apple"]
    ground_truths = ["apple", "apple", "apple"]
    robustness_scorer = WeaveRobustnessScorer(
        use_exact_match=True,
        device="cpu",
        model_name_or_path="",
        use_ground_truths=True,
    )
    result = robustness_scorer.score(
        reference_text=reference_text, texts=texts, ground_truths=ground_truths
    )
    assert truncate(result["cohen_h"], 5) == 0.60817


def test_robustness_scorer_with_ground_truths_as_booleans():
    reference_text = "True"
    texts = ["True", "False", "True"]
    ground_truths = [
        False,
        False,
        False,
    ]  # Booleans will be converted to strings
    robustness_scorer = WeaveRobustnessScorer(
        use_exact_match=True,
        device="cpu",
        model_name_or_path="",
        use_ground_truths=True,
    )
    result = robustness_scorer.score(
        reference_text=reference_text, texts=texts, ground_truths=ground_truths
    )
    assert truncate(result["cohen_h"], 5) == 0.39182


def test_robustness_scorer_ground_truths_length_mismatch():
    reference_text = "True"
    texts = ["True", "False", "True"]
    ground_truths = ["True", "True"]  # Mismatched length
    robustness_scorer = WeaveRobustnessScorer(use_ground_truths=True)
    with pytest.raises(
        AssertionError, match="Length of ground_truths must match the length of output."
    ):
        robustness_scorer.score(
            reference_text=reference_text, texts=texts, ground_truths=ground_truths
        )


def test_robustness_scorer_ground_truths_edge_case():
    reference_text = "True"
    texts = []
    ground_truths = ["True"]
    robustness_scorer = WeaveRobustnessScorer(use_ground_truths=True)
    with pytest.raises(
        AssertionError,
        match="There are no `texts`, there must be at least one text to measure against.",
    ):
        robustness_scorer.score(
            reference_text=reference_text, texts=texts, ground_truths=ground_truths
        )


def test_robustness_scorer_non_binary():
    # Example outputs with original and perturbed sentences
    reference_text = "The quick brown fox jumps over the lazy dog."
    texts = [
        "A fast dark fox leaps over a sleepy canine.",
        "The quick brown fox hops over the lazy dog.",
        "An agile red fox jumps over the lazy hound.",
    ]

    # Instantiate the scorer with binary=False
    robustness_scorer = WeaveRobustnessScorer(use_exact_match=False)

    # Run the scorer's `score` method
    result = robustness_scorer.score(reference_text=reference_text, texts=texts)

    print(result)

    # Assert that the result contains 'cohen_d' and is a float
    assert "cohen_d" in result
    assert isinstance(result["cohen_d"], float)

    # Check that the effect size is within a reasonable range
    assert (
        0 <= abs(result["cohen_d"]) <= 3
    ), f"Cohen's d is out of expected range: {result['cohen_d']}"


def test_robustness_scorer_non_binary_with_ground_truths():
    # Outputs from the model
    reference_text = "The capital of France is Paris."
    texts = [
        "Paris is the capital city of France.",
        "France's capital is Paris.",
        "The capital city of France is Paris.",
    ]

    # Ground truths corresponding to each output
    ground_truths = ["Paris", "Paris", "Paris"]

    # Instantiate the scorer with binary=False
    robustness_scorer = WeaveRobustnessScorer(use_exact_match=False)

    # Run the scorer's `score` method
    result = robustness_scorer.score(
        reference_text=reference_text, texts=texts, ground_truths=ground_truths
    )

    print(result)

    # Assert that the result contains 'cohen_d' and is a float
    assert "cohen_d" in result
    assert isinstance(result["cohen_d"], float)

    # Check that the effect size is within a reasonable range
    assert (
        0 <= abs(result["cohen_d"]) <= 3
    ), f"Cohen's d is out of expected range: {result['cohen_d']}"


def test_robustness_scorer_invalid_similarity_metric():
    reference_text = "Text A"
    texts = ["Text B"]
    robustness_scorer = WeaveRobustnessScorer(
        use_exact_match=False, similarity_metric="invalid_metric"
    )

    with pytest.raises(
        ValueError, match="Unsupported similarity metric: invalid_metric"
    ):
        robustness_scorer.score(reference_text=reference_text, texts=texts)


def test_robustness_scorer_zero_variance():
    reference_text = "The quick brown fox jumps over the lazy dog."
    texts = [
        "The quick brown fox jumps over the lazy dog.",
        "The quick brown fox jumps over the lazy dog.",
        "The quick brown fox jumps over the lazy dog.",
    ]

    robustness_scorer = WeaveRobustnessScorer(use_exact_match=False)
    result = robustness_scorer.score(reference_text=reference_text, texts=texts)

    # Since all outputs are identical, differences are zero, and std_dev is zero
    assert result["cohen_d"] == 0.0


def test_robustness_scorer_long_texts():
    reference_text = (
        "In a village of La Mancha, the name of which I have no desire to call to mind, "
        "there lived not long since one of those gentlemen that keep a lance in the lance-rack, "
        "an old buckler, a lean hack, and a greyhound for coursing."
    )
    texts = [
        "In a small town in La Mancha, whose name I don't care to remember, there lived not long ago "
        "one of those gentlemen who always have a lance and ancient shield on a shelf, "
        "a skinny nag, and a greyhound for hunting.",
        "In a certain village in La Mancha, which I shall not name, there lived recently a gentleman "
        "who kept a spear in his rack, an old shield, a thin horse, and a hunting greyhound.",
    ]

    robustness_scorer = WeaveRobustnessScorer(use_exact_match=False)
    result = robustness_scorer.score(reference_text=reference_text, texts=texts)

    # Assert that the scorer returns a valid effect size
    assert "cohen_d" in result
    assert isinstance(result["cohen_d"], float)


def test_robustness_scorer_unicode_texts():
    reference_text = "C'est la vie 😊"  # Original output with emoji
    texts = [
        "C'est la vie 😊",  # Identical perturbed output
        "C'est la vie 😢",  # Perturbed output with different emoji
        "C'est la vie",  # Perturbed output without emoji
    ]

    robustness_scorer = WeaveRobustnessScorer(use_exact_match=False)
    result = robustness_scorer.score(reference_text=reference_text, texts=texts)

    # Assert that the scorer computes a valid effect size
    assert "cohen_d" in result
    assert isinstance(result["cohen_d"], float)


def test_robustness_scorer_compute_similarity_exception():
    reference_text = "Text A"
    texts = ["Text B"]
    robustness_scorer = WeaveRobustnessScorer(use_exact_match=False)

    # Mock the embedding model to raise an exception
    def mock_encode(*args, **kwargs):
        raise RuntimeError("Mocked exception in embedding model.")

    robustness_scorer.embedding_model.encode = mock_encode

    with pytest.raises(RuntimeError, match="Mocked exception in embedding model."):
        robustness_scorer.score(reference_text=reference_text, texts=texts)


def test_robustness_scorer_mixed_data_types():
    reference_text = "42"
    texts = [42, True, None]

    robustness_scorer = WeaveRobustnessScorer(
        use_exact_match=True,
        device="cpu",
        model_name_or_path="",
    )

    # Since outputs are converted to strings, this should work
    result = robustness_scorer.score(reference_text=reference_text, texts=texts)

    # Assert that the scorer computes a valid effect size
    assert "cohen_h" in result
    assert isinstance(result["cohen_h"], float)


def test_robustness_scorer_multilingual_texts():
    reference_text = "Hello, how are you?"  # English
    texts = [
        "Hola, ¿cómo estás?",  # Spanish
        "Bonjour, comment ça va?",  # French
        "こんにちは、お元気ですか？",  # Japanese
    ]

    robustness_scorer = WeaveRobustnessScorer(use_exact_match=False)
    result = robustness_scorer.score(reference_text=reference_text, texts=texts)

    # Since texts are in different languages, expect low similarities
    assert result["score(perturbed)"] < 0.5


def test_interpretation_strings():
    reference_text = "The capital of France is Paris."
    texts = ["Paris is the capital of France."]
    scorer = WeaveRobustnessScorer(
        use_exact_match=True,
        device="cpu",
        model_name_or_path="",
        return_interpretation=True,
    )
    result = scorer.score(reference_text=reference_text, texts=texts)
    assert "interpretation" in result
    assert isinstance(result["interpretation"], str)


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
        reference_text = questions[0]
        texts = questions[1:]
        return robustness_scorer.score(reference_text=reference_text, texts=texts)

    robustness_scorer = WeaveRobustnessScorer()

    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[robustness_scorer],
    )
    result = await evaluation.evaluate(model)
    assert truncate(result["WeaveRobustnessScorer"]["cohen_h"]["mean"], 5) == 0.49999


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
        reference_text = questions[0]
        texts = questions[1:]
        return robustness_scorer.score(reference_text=reference_text, texts=texts)

    # Instantiate the WeaveRobustnessScorer
    robustness_scorer = WeaveRobustnessScorer(use_ground_truths=True)

    # Perform evaluation using Weave's Evaluation framework
    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[robustness_scorer],
    )
    result = await evaluation.evaluate(model)

    # Check that Cohen's h is computed as expected
    assert "WeaveRobustnessScorer" in result, "Scorer results are missing."
    cohen_h_mean = truncate(result["WeaveRobustnessScorer"]["cohen_h"]["mean"], 5)
    assert cohen_h_mean == 0.24999, f"Unexpected Cohen's h mean: {cohen_h_mean}"


@pytest.mark.asyncio
async def test_robustness_scorer_non_binary_evaluation():
    # Simulated dataset with questions (original and perturbed)
    dataset = [
        {
            "questions": [
                "What is the capital of France?",  # Original question
                "What's the capital of France?",  # Perturbed question 1
                "What is France's capital city?",  # Perturbed question 2
            ],
        },
        {
            "questions": [
                "Who is the CEO of Apple?",  # Original question
                "Who leads Apple Inc.?",  # Perturbed question 1
                "Name the chief executive of Apple.",  # Perturbed question 2
            ],
        },
    ]

    @weave.op
    def model(questions: list[str]):
        reference_text = questions[0]
        texts = questions[1:]
        return robustness_scorer.score(reference_text=reference_text, texts=texts)

    # Instantiate the WeaveRobustnessScorer with binary=False
    robustness_scorer = WeaveRobustnessScorer(use_exact_match=False)

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
    print(result["WeaveRobustnessScorer"])

    # Assert that the 'cohen_d' is present and is a float
    assert "cohen_d" in result["WeaveRobustnessScorer"]
    assert isinstance(result["WeaveRobustnessScorer"]["cohen_d"]["mean"], float)

    # Optionally, you can check that the effect size is within a reasonable range
    cohen_d_mean = result["WeaveRobustnessScorer"]["cohen_d"]["mean"]
    assert (
        0 <= abs(cohen_d_mean) <= 3
    ), f"Cohen's d mean is out of expected range: {cohen_d_mean}"


@pytest.mark.parametrize(
    "input_text",
    [
        "The quick brown fox jumps over the lazy dog.",
        "Hello, world!",
        "123 Testing...",
        "",
    ],
)
def test_butterfingers(input_text):
    perturbed = butterfingers(input_text)
    assert isinstance(perturbed, str)
    assert len(perturbed) == len(input_text)


@pytest.mark.parametrize(
    "input_text",
    [
        "The quick brown fox jumps over the lazy dog.",
        "Hello, world!",
        "123 Testing...",
        "",
    ],
)
def test_add_whitespace(input_text):
    perturbed = add_whitespace(input_text)
    assert isinstance(perturbed, str)
    assert len(perturbed) >= len(input_text)


@pytest.mark.parametrize(
    "input_text",
    [
        "The quick brown fox jumps over the lazy dog.",
        "Hello, world!",
        "123 Testing...",
        "",
    ],
)
def test_swap_chars(input_text):
    perturbed = swap_chars(input_text)
    assert isinstance(perturbed, str)
    assert len(perturbed) == len(input_text)


@pytest.mark.parametrize(
    "input_text",
    [
        "The quick brown fox jumps over the lazy dog.",
        "Hello, world!",
        "123 Testing...",
        "",
    ],
)
def test_remove_punctuation(input_text):
    perturbed = remove_punctuation(input_text)
    assert isinstance(perturbed, str)
    assert all(c not in string.punctuation for c in perturbed)


@pytest.mark.parametrize(
    "input_text",
    [
        "The quick brown fox jumps over the lazy dog.",
        "Hello, world!",
        "123 Testing...",
        "",
    ],
)
def test_random_case_change(input_text):
    perturbed = random_case_change(input_text)
    assert isinstance(perturbed, str)


@pytest.mark.parametrize(
    "input_text",
    [
        "The quick brown fox jumps over the lazy dog.",
        "Hello, world!",
        "123 Testing...",
        "",
    ],
)
def test_random_capitalization(input_text):
    perturbed = random_capitalization(input_text)
    assert isinstance(perturbed, str)


@pytest.mark.parametrize(
    "input_text",
    [
        "The quick brown fox jumps over the lazy dog.",
        "Hello, world!",
        "123 Testing...",
        "",
    ],
)
def test_text_noise(input_text):
    perturbed = text_noise(input_text)
    assert isinstance(perturbed, str)
    assert len(perturbed) == len(input_text) + 1  # Noise adds a single character


@pytest.mark.parametrize(
    "input_text",
    [
        "The quick brown fox jumps over the lazy dog.",
        "Hello, world!",
        "123 Testing...",
        "",
    ],
)
def test_split_merge_words(input_text):
    perturbed = split_merge_words(input_text)
    assert isinstance(perturbed, str)


@pytest.mark.parametrize(
    "input_text",
    [
        "The quick brown fox jumps over the lazy dog.",
        "Hello, world!",
        "123 Testing...",
        "",
    ],
)
def test_emphasize_words(input_text):
    perturbed = emphasize_words(input_text)
    assert isinstance(perturbed, str)


def test_create_perturbed_dataset():
    dataset = [
        "What is the capital of France?",
        "Who is the CEO of Tesla?",
    ]
    num_perturbations = 5
    perturbed_dataset = create_perturbed_dataset(dataset, num_perturbations)

    assert len(perturbed_dataset) == len(dataset)
    for original, perturbed in zip(dataset, perturbed_dataset):
        assert "questions" in perturbed
        questions = perturbed["questions"]
        assert len(questions) == num_perturbations + 1  # Original + perturbations
        assert questions[0] == original  # First question is the original text
        assert all(isinstance(q, str) for q in questions)


def test_create_perturbed_dataset_empty():
    dataset = []
    perturbed_dataset = create_perturbed_dataset(dataset, 5)
    assert perturbed_dataset == []


def test_create_perturbed_dataset_single_item():
    dataset = ["What is the capital of Germany?"]
    num_perturbations = 3
    perturbed_dataset = create_perturbed_dataset(dataset, num_perturbations)

    assert len(perturbed_dataset) == 1
    assert "questions" in perturbed_dataset[0]
    questions = perturbed_dataset[0]["questions"]
    assert len(questions) == num_perturbations + 1  # Original + perturbations
    assert questions[0] == dataset[0]  # Original text


def test_create_perturbed_dataset_randomness():
    dataset = ["What is the capital of Germany?"]
    num_perturbations = 3

    # Generate two datasets and check they are not identical
    perturbed_dataset_1 = create_perturbed_dataset(dataset, num_perturbations)
    perturbed_dataset_2 = create_perturbed_dataset(dataset, num_perturbations)

    assert perturbed_dataset_1 != perturbed_dataset_2  # Due to randomness
