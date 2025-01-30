import pytest  # type: ignore

from weave.scorers import AccuracyScorer


def test_binary_accuracy():
    """Test binary accuracy scoring and summarization."""
    scorer = AccuracyScorer(task="binary")

    # Test score method
    assert scorer.score(output=1, ground_truth=1)["score"] == 1.0
    assert scorer.score(output=0, ground_truth=1)["score"] == 0.0

    # Test summarize method
    score_rows = [
        {"score": 1.0, "output": 1, "ground_truth": 1},
        {"score": 0.0, "output": 0, "ground_truth": 1},
    ]
    summary = scorer.summarize(score_rows)
    assert summary == {"accuracy": 0.5}


def test_multiclass_accuracy_micro():
    """Test multiclass accuracy scoring with micro averaging."""
    scorer = AccuracyScorer(task="multiclass", num_classes=3, average="micro")

    # Test score method
    assert scorer.score(output=2, ground_truth=2)["score"] == 1.0
    assert scorer.score(output=1, ground_truth=2)["score"] == 0.0

    # Test summarize method
    score_rows = [
        {"score": 1.0, "output": 2, "ground_truth": 2},
        {"score": 0.0, "output": 1, "ground_truth": 2},
        {"score": 1.0, "output": 0, "ground_truth": 0},
    ]
    summary = scorer.summarize(score_rows)
    assert summary["accuracy"] == 2 / 3


def test_multiclass_accuracy_macro():
    """Test multiclass accuracy scoring with macro averaging."""
    scorer = AccuracyScorer(task="multiclass", num_classes=3, average="macro")

    # Test summarize method
    score_rows = [
        {"score": 1.0, "output": 2, "ground_truth": 2},
        {"score": 1.0, "output": 1, "ground_truth": 1},
        {"score": 0.0, "output": 0, "ground_truth": 2},
        {"score": 1.0, "output": 0, "ground_truth": 0},
    ]
    summary = scorer.summarize(score_rows)
    assert summary["accuracy"] == pytest.approx((1.0 + 1.0 + 0.5) / 3)


def test_multilabel_accuracy_micro():
    """Test multilabel accuracy scoring with micro averaging."""
    scorer = AccuracyScorer(task="multilabel", average="micro")

    # Test score method
    assert scorer.score(output=[1, 0, 1], ground_truth=[1, 0, 1])["score"] == 1.0
    assert scorer.score(output=[1, 0, 0], ground_truth=[1, 0, 1])["score"] == 0.0

    # Test summarize method
    score_rows = [
        {"score": 1.0, "output": [1, 0, 1], "ground_truth": [1, 0, 1]},
        {"score": 0.0, "output": [1, 1, 0], "ground_truth": [1, 0, 1]},
    ]
    summary = scorer.summarize(score_rows)
    assert summary["accuracy"] == 0.5


def test_multilabel_accuracy_macro():
    """Test multilabel accuracy scoring with macro averaging."""
    scorer = AccuracyScorer(task="multilabel", average="macro")

    # Test summarize method
    score_rows = [
        {"score": 1.0, "output": [1, 0, 1], "ground_truth": [1, 0, 1]},
        {"score": 0.0, "output": [1, 1, 0], "ground_truth": [1, 0, 1]},
    ]
    summary = scorer.summarize(score_rows)
    assert summary["accuracy"] == pytest.approx((1.0 + 0.5 + 1.0) / 3)


def test_invalid_task():
    """Test invalid task handling."""
    with pytest.raises(ValueError, match="Unsupported task type"):
        AccuracyScorer(task="invalid_task")


def test_invalid_output_type_multiclass():
    """Test invalid output type for multiclass tasks."""
    scorer = AccuracyScorer(task="multiclass", num_classes=3)

    with pytest.raises(ValueError, match="predictions must be an integer"):
        scorer.score(output=[0, 1], ground_truth=1)


def test_invalid_output_type_multilabel():
    """Test invalid output type for multilabel tasks."""
    scorer = AccuracyScorer(task="multilabel")

    with pytest.raises(ValueError, match="predictions and ground truth must be lists of labels"):
        scorer.score(output=1, ground_truth=[1, 0, 1])
