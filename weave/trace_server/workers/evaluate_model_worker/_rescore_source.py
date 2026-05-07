"""Internal dataclass for the rescore worker — one row of source eval data
to be rescored under a new evaluation run.

Contract (mirrors normal eval predict_and_score per-row data):
    inputs_for_call  — value to set as ``example`` on the new predict_and_score
                        call's inputs. Preserves the source's TableRow ref form
                        when available so the frontend can deref it the same
                        way it does for the source eval.
    inputs_for_scorer — already-dereffed dict to pass to ``apply_scorer_async``.
                        For dataset-backed evals this is the resolved row dict;
                        for imperative evals it equals inputs_for_call.
    output            — model output as recorded on the source's
                        ``predict_and_score.output["output"]``.
    model_latency     — copied from the source so the new trace shows the
                        same per-row latency the original run measured.
    source_predict    — content snapshot of the source row's predict subcall,
                        used to emit a faithful synthetic predict under the new
                        pas (same op_name, inputs, output, summary, duration).
                        ``None`` for imperative sources that emitted no predict.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class _SourcePredict:
    """Content snapshot of one source predict call.

    Used to emit a faithful synthetic predict under a new predict_and_score:
    we copy op_name/inputs/output/summary verbatim and preserve the duration
    (``ended_at - started_at``) while shifting both timestamps into the new
    eval's wall-clock window. The new call is a fresh record (new id, new
    trace_id, new parent) — content fidelity, not identity.
    """

    op_name: str
    inputs: dict[str, Any]
    output: Any
    started_at: datetime.datetime
    ended_at: datetime.datetime
    summary: dict[str, Any]


@dataclass
class _RescoreSource:
    inputs_for_call: Any
    inputs_for_scorer: dict[str, Any]
    output: Any
    model_latency: float
    source_predict: _SourcePredict | None = None
