import asyncio

import pytest

import weave
from weave import Evaluation
from weave.scorers import MultiTaskBinaryClassificationF1


def test_multiclass_f1_score(client):
    evaluation = Evaluation(
        dataset=[{"target": {"a": False, "b": True}, "pred": {"a": True, "b": False}}],
        scorers=[MultiTaskBinaryClassificationF1(class_names=["a", "b"])],
    )

    @weave.op()
    def return_pred(pred):
        return pred

    result = asyncio.run(evaluation.evaluate(return_pred))
    assert result == {
        "model_output": {
            "a": {"true_count": 1, "true_fraction": 1.0},
            "b": {"true_count": 0, "true_fraction": 0.0},
        },
        "MultiTaskBinaryClassificationF1": {
            "a": {"f1": 0, "precision": 0.0, "recall": 0},
            "b": {"f1": 0, "precision": 0, "recall": 0.0},
        },
        "model_latency": {
            "mean": pytest.approx(0, abs=1),
        },
    }
