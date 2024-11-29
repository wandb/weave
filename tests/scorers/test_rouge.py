import pytest
from weave.scorers import RougeScorer  # Replace with your actual module path

def test_rouge_scorer_initialization():
    """Test that RougeScorer initializes correctly."""
    scorer = RougeScorer()
    assert scorer.rouge_scorer is not None

def test_rouge_scorer_missing_rouge_package(monkeypatch):
    """Test that an ImportError is raised if the Rouge package is missing."""
    def mock_import_rouge(*args, **kwargs):
        raise ImportError

    monkeypatch.setattr("rouge.Rouge", mock_import_rouge)

    with pytest.raises(
        ImportError, match="`rouge` is not installed. Please install it with `pip install rouge`"
    ):
        RougeScorer()

def test_rouge_scorer_score_success():
    """Test the score method with valid inputs."""
    scorer = RougeScorer()
    ground_truth = "The quick brown fox jumps over the lazy dog."
    output = "A quick brown fox leaps over a sleepy dog."
    result = scorer.score(ground_truth, output)

    # Expected result depends on the rouge library's internal logic
    assert "rouge-1" in result
    assert "rouge-2" in result
    assert "rouge-l" in result
    assert 0 <= result["rouge-1"] <= 1
    assert 0 <= result["rouge-2"] <= 1
    assert 0 <= result["rouge-l"] <= 1

def test_rouge_scorer_score_empty_strings():
    """Test that score works with empty strings."""
    scorer = RougeScorer()
    result = scorer.score("", "")

    assert result == {
        "rouge-1": 0.0,
        "rouge-2": 0.0,
        "rouge-l": 0.0,
    }

def test_rouge_scorer_score_none_inputs():
    """Test that score raises an assertion error if inputs are None."""
    scorer = RougeScorer()
    with pytest.raises(AssertionError, match="`ground_truth` and `output` cannot be None"):
        scorer.score(None, None)

def test_rouge_scorer_partial_overlap():
    """Test the score method with partial overlap."""
    scorer = RougeScorer()
    ground_truth = "The cat sat on the mat."
    output = "The cat is sitting on the mat."
    result = scorer.score(ground_truth, output)

    assert "rouge-1" in result
    assert "rouge-2" in result
    assert "rouge-l" in result
    assert 0 <= result["rouge-1"] <= 1
    assert 0 <= result["rouge-2"] <= 1
    assert 0 <= result["rouge-l"] <= 1

def test_rouge_scorer_high_overlap():
    """Test the score method with high overlap."""
    scorer = RougeScorer()
    ground_truth = "The quick brown fox jumps over the lazy dog."
    output = "The quick brown fox jumps over the lazy dog."
    result = scorer.score(ground_truth, output)

    assert result["rouge-1"] == pytest.approx(1.0, rel=1e-3)
    assert result["rouge-2"] == pytest.approx(1.0, rel=1e-3)
    assert result["rouge-l"] == pytest.approx(1.0, rel=1e-3)

def test_rouge_scorer_no_overlap():
    """Test the score method with no overlap."""
    scorer = RougeScorer()
    ground_truth = "The cat sat on the mat."
    output = "An entirely different sentence."
    result = scorer.score(ground_truth, output)

    assert result["rouge-1"] == pytest.approx(0.0, rel=1e-3)
    assert result["rouge-2"] == pytest.approx(0.0, rel=1e-3)
    assert result["rouge-l"] == pytest.approx(0.0, rel=1e-3)