r"""Manual test for the GEPA integration's error-tracking surface.

Runs `gepa.optimize()` against an adapter that deliberately raises on a
couple of minibatch evaluations. GEPA catches those at the engine level
(because `raise_on_exception=False`) and dispatches `on_error`. Our
integration records the error on the span where it actually happened
(typically `gepa.evaluate` — the call that ran when the exception was
raised) rather than creating a separate error span. That avoids logging
the same exception twice while still giving you a clickable, filterable
error record with full GEPA context (iteration, `will_continue`, etc.)
in the span's output.

Usage (from repo root):

    # Offline: stub reflection LM, no API calls.
    uv run --extra gepa python try_gepa_errors.py

Env vars:
    WEAVE_PROJECT       — Weave project (default: "gepa-errors-smoketest").
    GEPA_ERROR_ITERS    — comma-separated iteration numbers on which the
                          adapter should explode (default: "1,3").
    GEPA_BUDGET         — metric-call budget (default: 20).

Click through in the Weave UI after the run:

    1. Traces tab  — filter by status=error and op_name prefix `gepa.`
                     to count / list every exception the run hit.
    2. Click any errored `gepa.evaluate` span: the full exception and
                     traceback are on the call, and its `output` carries
                     the engine metadata (iteration, exception_type,
                     exception_message, will_continue).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

import gepa
from gepa.core.adapter import EvaluationBatch

import weave


class FlakyAdapter:
    """Adapter that scores by instruction length, but raises on specific
    evaluation calls so we can exercise the error-tracking path.

    `_fail_on_call_counts` is the set of 1-indexed evaluate() calls that
    should raise. Call 1 is the seed's full-valset eval (we always let that
    one succeed so the run can start); subsequent calls are proposer
    minibatch evaluations.
    """

    def __init__(self, fail_on_call_counts: set[int]) -> None:
        self._fail_on_call_counts = fail_on_call_counts
        self._call_count = 0

    # Must be set at class-level or the reflective-mutation proposer
    # explicitly skips the reflection LM path.
    propose_new_texts = None

    def evaluate(
        self,
        batch: Sequence[Any],
        candidate: dict[str, str],
        capture_traces: bool = False,
    ) -> EvaluationBatch:
        self._call_count += 1
        if self._call_count in self._fail_on_call_counts:
            raise RuntimeError(
                f"simulated evaluation failure (call #{self._call_count})"
            )
        text = candidate.get("instructions", "")
        score = max(0.0, 1.0 - min(1.0, len(text) / 100.0))
        outputs = [f"answered: {ex!r}" for ex in batch]
        scores = [score for _ in batch]
        trajectories = (
            [{"candidate_len": len(text), "example": ex} for ex in batch]
            if capture_traces
            else None
        )
        return EvaluationBatch(
            outputs=outputs, scores=scores, trajectories=trajectories
        )

    def make_reflective_dataset(
        self,
        candidate: dict[str, str],
        eval_batch: EvaluationBatch,
        components_to_update: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            component: [
                {
                    "Inputs": {"text": candidate.get(component, "")},
                    "Outputs": out,
                    "Score": score,
                    "Feedback": "Shorter is better.",
                }
                for out, score in zip(
                    eval_batch.outputs, eval_batch.scores, strict=True
                )
            ]
            for component in components_to_update
        }


@weave.op
def stub_reflection_lm(prompt: str | list[dict[str, Any]]) -> str:
    return "```\nBe brief.\n```"


def main() -> None:
    project = os.getenv("WEAVE_PROJECT", "gepa-errors-smoketest")
    budget = int(os.getenv("GEPA_BUDGET", "20"))
    error_iters = {
        int(x.strip())
        for x in os.getenv("GEPA_ERROR_ITERS", "1,3").split(",")
        if x.strip()
    }
    # The adapter counts `evaluate()` calls 1-indexed; call 1 is the seed
    # full-valset eval which we must let succeed. Map the requested
    # iteration-level failures to call indices by adding 1 (seed) + 2*(iter-1)
    # (iterations do roughly 2 evals each: current-on-minibatch, proposed-
    # on-minibatch). Being approximate is fine — the point is to surface
    # errors, not line them up exactly.
    fail_calls = {1 + 2 * (i - 1) + 1 for i in error_iters if i >= 1}

    weave.init(project)

    print(f"Budget: {budget} metric calls")
    print(f"Requested error iterations: {sorted(error_iters)}")
    print(f"Translated to evaluate() call indices to fail: {sorted(fail_calls)}")
    print()

    gepa.optimize(
        seed_candidate={"instructions": "Please answer carefully."},
        trainset=[{"q": f"train-{i}"} for i in range(4)],
        valset=[{"q": f"val-{i}"} for i in range(2)],
        adapter=FlakyAdapter(fail_on_call_counts=fail_calls),
        reflection_lm=stub_reflection_lm,
        max_metric_calls=budget,
        display_progress_bar=False,
        raise_on_exception=False,
        skip_perfect_score=False,
    )

    print()
    print("=== Run complete ===")
    print()
    print("Open the Weave trace URL printed above. What to check:")
    print("  1. Traces tab — filter by status=error. You should see one row")
    print("     per failed call (the `gepa.evaluate` span that raised).")
    print("  2. Click an errored span — the full exception and traceback are")
    print("     attached, and the `output` field has the engine-level")
    print("     metadata (iteration, exception_type, exception_message,")
    print("     will_continue).")
    print("  3. No separate `gepa.error.*` sibling spans: each exception is")
    print("     recorded on the span that actually raised it.")


if __name__ == "__main__":
    main()
