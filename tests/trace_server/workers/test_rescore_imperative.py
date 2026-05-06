"""Tests for the rescore worker's imperative branch.

The killer test (where ``prediction_id != parent_call_id`` and scores must
attach to ``parent_call_id``) lives in this file once the imperative branch
is wired up. For now it covers the ``_RescoreSource`` dataclass shape, which
is the contract both branches share.
"""

from __future__ import annotations

from weave.trace_server.workers.evaluate_model_worker._rescore_source import (
    _RescoreSource,
)


def test_rescore_source_shape() -> None:
    src = _RescoreSource(
        prediction_id="p-1",
        parent_call_id="pas-1",
        inputs={"q": "x"},
        output={"y": "z"},
    )
    assert src.prediction_id == "p-1"
    assert src.parent_call_id == "pas-1"
    assert src.inputs == {"q": "x"}
    assert src.output == {"y": "z"}


def test_rescore_source_supports_unequal_ids() -> None:
    """Standard branch: ``prediction_id`` and ``parent_call_id`` are different calls."""
    src = _RescoreSource(
        prediction_id="prediction-call",
        parent_call_id="predict-and-score-call",
        inputs={},
        output=None,
    )
    assert src.prediction_id != src.parent_call_id


def test_rescore_source_supports_equal_ids() -> None:
    """Imperative branch: ``prediction_id == parent_call_id`` (the predict_and_score call)."""
    src = _RescoreSource(
        prediction_id="pas-1",
        parent_call_id="pas-1",
        inputs={"example": {"q": "x"}},
        output={"output": "y"},
    )
    assert src.prediction_id == src.parent_call_id
