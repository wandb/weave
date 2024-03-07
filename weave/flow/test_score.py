import pytest

from weave.flow.scorer import MulticlassF1Score


def test_multiclass_f1():
    scorer = MulticlassF1Score(class_names=["a", "b"])
    data = [
        {"label": {"a": 1, "b": 0}, "prediction": {"a": 1, "b": 0}},
        {"label": {"a": 1, "b": 0}, "prediction": {"a": 0, "b": 0}},
        {"label": {"a": 0, "b": 1}, "prediction": {"a": 0, "b": 1}},
        {"label": {"a": 0, "b": 1}, "prediction": {"a": 0, "b": 1}},
        {"label": {"a": 0, "b": 1}, "prediction": {"a": 0, "b": 1}},
        {"label": {"a": 0, "b": 1}, "prediction": {"a": 0, "b": 0}},
    ]
    scores = [scorer.score(row["label"], row["prediction"]) for row in data]
    result = scorer.summarize(scores)
    assert result == {
        "a": {"f1": 0.6666666666666666, "precision": 1.0, "recall": 0.5},
        "b": {"f1": 0.8571428571428571, "precision": 1.0, "recall": 0.75},
    }
