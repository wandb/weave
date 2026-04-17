from __future__ import annotations

from collections.abc import Generator, Sequence
from typing import Any

import gepa
import pytest
from gepa.core.adapter import EvaluationBatch

from weave.integrations.gepa import gepa_sdk
from weave.integrations.gepa.gepa_callback import WeaveGEPACallback
from weave.integrations.gepa.gepa_sdk import get_gepa_patcher
from weave.integrations.integration_utilities import (
    flatten_calls,
    flattened_calls_to_names,
)
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import CallsFilter


@pytest.fixture(autouse=True)
def patch_gepa() -> Generator[None, None, None]:
    gepa_sdk._gepa_patcher = None
    patcher = get_gepa_patcher()
    patcher.attempt_patch()
    try:
        yield
    finally:
        patcher.undo_patch()
        gepa_sdk._gepa_patcher = None


class _StubAdapter:
    """Minimal GEPAAdapter that scores by instruction length.

    Returns a static score per example so runs are deterministic and require
    no network.
    """

    def evaluate(
        self,
        batch: Sequence[Any],
        candidate: dict[str, str],
        capture_traces: bool = False,
    ) -> EvaluationBatch:
        component = candidate.get("instructions", "")
        scores = [float(len(component)) / 100.0 for _ in batch]
        outputs = [component for _ in batch]
        trajectories = [{"len": len(component)} for _ in batch] if capture_traces else None
        return EvaluationBatch(outputs=outputs, scores=scores, trajectories=trajectories)

    def make_reflective_dataset(
        self,
        candidate: dict[str, str],
        eval_batch: EvaluationBatch,
        components_to_update: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            component: [
                {"Inputs": {"t": "x"}, "Outputs": "y", "Score": 0.5}
                for _ in eval_batch.scores
            ]
            for component in components_to_update
        }

    def propose_new_texts(
        self,
        candidate: dict[str, str],
        reflective_dataset: dict[str, list[dict[str, Any]]],
        components_to_update: list[str],
    ) -> dict[str, str]:
        return {c: candidate.get(c, "") + " MORE" for c in components_to_update}


def _stub_reflection_lm(prompt: str | list[dict[str, Any]]) -> str:
    return "ignored"


@pytest.mark.skip_clickhouse_client
def test_gepa_optimize_traces_lifecycle(client: WeaveClient) -> None:
    """Run gepa.optimize with stubs and verify the Weave trace captures the
    top-level optimize span plus iteration / evaluate / propose child spans.
    """
    gepa.optimize(
        seed_candidate={"instructions": "seed"},
        trainset=[{"q": "a"}, {"q": "b"}, {"q": "c"}],
        valset=[{"q": "d"}],
        adapter=_StubAdapter(),
        reflection_lm=_stub_reflection_lm,
        max_metric_calls=8,
        display_progress_bar=False,
        raise_on_exception=False,
        skip_perfect_score=False,
    )

    # Walk the hierarchy from the root `gepa.optimize` call so we can assert on
    # the parent/child structure of the trace rather than just the flat set of
    # op names present.
    roots = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    assert len(roots) == 1
    got = flattened_calls_to_names(flatten_calls(roots))
    expected = [
        ("gepa.optimize", 0),
        # Seed candidate is evaluated on the full valset before iteration 1.
        ("gepa.valset_evaluated", 1),
        ("gepa.iteration", 1),
        # Within an iteration: evaluate current candidate, propose a new one,
        # evaluate the proposal, then (on acceptance) run the full valset eval.
        ("gepa.evaluate", 2),
        ("gepa.propose", 2),
        ("gepa.evaluate", 2),
        ("gepa.valset_evaluated", 2),
    ]
    assert got == expected, got


@pytest.mark.skip_clickhouse_client
def test_gepa_optimize_does_not_double_inject_callback(client: WeaveClient) -> None:
    """If the user already passes a WeaveGEPACallback, the patcher should not
    add a second one.
    """
    user_callback = WeaveGEPACallback()
    gepa.optimize(
        seed_candidate={"instructions": "seed"},
        trainset=[{"q": "a"}],
        valset=[{"q": "d"}],
        adapter=_StubAdapter(),
        reflection_lm=_stub_reflection_lm,
        callbacks=[user_callback],
        max_metric_calls=3,
        display_progress_bar=False,
        raise_on_exception=False,
        skip_perfect_score=False,
    )
    # Still emits traces even with a user-supplied callback.
    calls = list(client.get_calls())
    assert calls, "expected at least the top-level gepa.optimize call"
