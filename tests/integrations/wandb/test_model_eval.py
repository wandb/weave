"""Tests for ModelEvaluationLogger — marker tagging, column validation, and log_table.

Most tests require wandb and a live Weave client (the ``client`` fixture).
Column validation tests create a ModelEvaluationLogger but raise before any
network I/O, so they still need the client fixture for logger initialisation.
"""

from __future__ import annotations

import pytest

from weave.integrations.integration_utilities import op_name_from_call
from weave.integrations.wandb.model_eval import ModelEvaluationLogger

wandb = pytest.importorskip("wandb")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _eval_call(calls):
    """Return the top-level Evaluation.evaluate call from a call list."""
    return next(c for c in calls if op_name_from_call(c) == "Evaluation.evaluate")


# ---------------------------------------------------------------------------
# Marker tests
# ---------------------------------------------------------------------------


def test_model_eval_marker_on_evaluate_call(client):
    """The top-level Evaluation.evaluate call carries the model_eval marker."""
    ev = ModelEvaluationLogger(name="marker-test")
    ev.log_example(
        inputs={"image": "cat.png", "truth": "cat"},
        output={"predicted": "cat", "confidence": 0.97},
        scores={"correct": True},
    )
    ev.log_summary({"accuracy": 1.0})
    client.flush()

    eval_call = _eval_call(client.get_calls())
    attrs = eval_call.attributes or {}
    meta = attrs.get("_weave_eval_meta", {})
    assert meta.get("imperative") is True
    assert meta.get("model_eval") is True


def test_model_eval_attributes_contents(client):
    """ModelEvaluationLogger.attributes has both imperative and model_eval flags."""
    ev = ModelEvaluationLogger(name="attrs-test")
    assert ev.attributes == {"_weave_eval_meta": {"imperative": True, "model_eval": True}}


# ---------------------------------------------------------------------------
# log_table tests
# ---------------------------------------------------------------------------


def test_log_table_basic(client):
    """log_table converts wandb.Table rows and logs them as examples."""
    table = wandb.Table(
        columns=["image", "truth", "predicted", "confidence", "correct", "calibrated_score"],
        data=[
            ["cat.png", "cat", "cat", 0.97, True, 0.95],
            ["dog.png", "dog", "dog", 0.88, True, 0.85],
            ["bird.png", "bird", "cat", 0.52, False, 0.30],
        ],
    )

    ev = ModelEvaluationLogger(name="log-table-test")
    ev.log_table(
        table,
        input_columns=["image", "truth"],
        output_columns=["predicted", "confidence"],
        score_columns=["correct", "calibrated_score"],
    )
    ev.log_summary({"accuracy": 2 / 3})
    client.flush()

    calls = client.get_calls()
    pas_calls = [
        c for c in calls if op_name_from_call(c) == "Evaluation.predict_and_score"
    ]
    assert len(pas_calls) == 3

    expected = [
        {"image": "cat.png", "truth": "cat"},
        {"image": "dog.png", "truth": "dog"},
        {"image": "bird.png", "truth": "bird"},
    ]
    for i, ex in enumerate(expected):
        assert pas_calls[i].inputs["example"] == ex

    assert pas_calls[2].output["scores"]["correct"] is False


# ---------------------------------------------------------------------------
# Column validation tests
# ---------------------------------------------------------------------------


_COLS = ["image", "truth", "predicted", "confidence", "correct", "calibrated_score"]
_INPUT = ["image", "truth"]
_OUTPUT = ["predicted", "confidence"]
_SCORE = ["correct", "calibrated_score"]


def _make_table(*extra_cols: str):
    return wandb.Table(columns=[*_COLS, *extra_cols], data=[])


def test_unknown_column_raises(client):
    ev = ModelEvaluationLogger(name="col-val-test")
    with pytest.raises(ValueError, match="do not exist in the table"):
        ev.log_table(_make_table(), ["image", "truth", "nonexistent"], _OUTPUT, _SCORE)


def test_unaccounted_table_column_raises(client):
    ev = ModelEvaluationLogger(name="col-val-test")
    with pytest.raises(ValueError, match="not listed in input_columns"):
        ev.log_table(_make_table("extra"), _INPUT, _OUTPUT, _SCORE)


def test_duplicate_column_warns(client):
    """A column in more than one list warns but still works."""
    import warnings

    table = wandb.Table(
        columns=_COLS,
        data=[["cat.png", "cat", "cat", 0.9, True, 0.88]],
    )
    ev = ModelEvaluationLogger(name="dup-col-test")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ev.log_table(
            table,
            input_columns=["image", "truth", "predicted"],  # 'predicted' duplicated
            output_columns=["predicted", "confidence"],
            score_columns=["correct", "calibrated_score"],
        )
    dup_warnings = [w for w in caught if "appears in more than one" in str(w.message)]
    assert len(dup_warnings) >= 1
