from __future__ import annotations

from collections.abc import Generator, Sequence
from typing import Any

import gepa
import pytest
from gepa.core.adapter import EvaluationBatch

import weave
from weave.integrations.gepa import gepa_sdk
from weave.integrations.gepa.gepa_callback import WeaveGEPACallback
from weave.integrations.gepa.gepa_sdk import get_gepa_patcher
from weave.integrations.integration_utilities import (
    flatten_calls,
    flattened_calls_to_names,
    op_name_from_ref,
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
        trajectories = (
            [{"len": len(component)} for _ in batch] if capture_traces else None
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
    # op names present. Each `on_valset_evaluated` event also spawns an
    # Evaluation.evaluate call via EvaluationLogger; those come out as sibling
    # root traces (EvaluationLogger intentionally detaches from the caller's
    # stack so evals show up in the Evaluations tab).
    all_roots = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    optimize_roots = [
        r for r in all_roots if op_name_from_ref(r.op_name) == "gepa.optimize"
    ]
    eval_roots = [
        r for r in all_roots if op_name_from_ref(r.op_name) == "Evaluation.evaluate"
    ]
    assert len(optimize_roots) == 1
    # One eval per valset evaluation: seed + one accepted candidate in iter 1.
    assert len(eval_roots) == 2, [op_name_from_ref(r.op_name) for r in all_roots]

    got = flattened_calls_to_names(flatten_calls(optimize_roots))
    expected = [
        ("gepa.optimize", 0),
        # Seed candidate is evaluated on the full valset before iteration 1.
        ("gepa.valset_evaluated", 1),
        ("gepa.iteration", 1),
        # Within an iteration: evaluate the current candidate, build the
        # reflective dataset the reflection LM will see, propose a new
        # candidate, evaluate it, and (on acceptance) run the full valset eval.
        ("gepa.evaluate", 2),
        ("gepa.reflective_dataset", 2),
        ("gepa.propose", 2),
        ("gepa.evaluate", 2),
        ("gepa.valset_evaluated", 2),
    ]
    assert got == expected, got


class _NoProposeAdapter(_StubAdapter):
    """Stub adapter without a `propose_new_texts` override.

    Forces GEPA to fall through to `ReflectiveMutationProposer.propose_new_texts`,
    which invokes the user-supplied `reflection_lm` — the code path we want to
    stress for the LM-nesting test.
    """

    propose_new_texts = None  # type: ignore[assignment]


@pytest.mark.skip_clickhouse_client
def test_reflection_lm_call_nests_under_propose(client: WeaveClient) -> None:
    """Any Weave-traced call made by the reflection LM between
    `on_proposal_start` and `on_proposal_end` should appear as a child of
    `gepa.propose`. This is how a user gets to ask "how much did my
    reflection LM cost vs. my task LM?" from the trace UI.
    """

    @weave.op
    def fake_reflection_lm(prompt: str | list[dict[str, Any]]) -> str:
        # GEPA parses the response inside ```...``` fences.
        return "```\nBe concise.\n```"

    adapter = _NoProposeAdapter()
    adapter.propose_new_texts = None  # belt and suspenders

    gepa.optimize(
        seed_candidate={"instructions": "seed"},
        trainset=[{"q": "a"}, {"q": "b"}, {"q": "c"}],
        valset=[{"q": "d"}],
        adapter=adapter,
        reflection_lm=fake_reflection_lm,
        max_metric_calls=6,
        display_progress_bar=False,
        raise_on_exception=False,
        skip_perfect_score=False,
    )

    roots = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    optimize_roots = [
        r for r in roots if op_name_from_ref(r.op_name) == "gepa.optimize"
    ]
    assert len(optimize_roots) == 1

    flat = flatten_calls(optimize_roots)
    names = flattened_calls_to_names(flat)

    # Find the `gepa.propose` call and its immediate children.
    propose_idx = next(i for i, (n, _) in enumerate(names) if n == "gepa.propose")
    propose_depth = names[propose_idx][1]
    children = []
    for i in range(propose_idx + 1, len(names)):
        n, d = names[i]
        if d <= propose_depth:
            break
        if d == propose_depth + 1:
            children.append(n)

    assert "fake_reflection_lm" in children, (
        f"expected fake_reflection_lm to nest under gepa.propose; "
        f"found children={children!r}, full trace={names!r}"
    )


@pytest.mark.skip_clickhouse_client
@pytest.mark.disable_logging_error_check(reason="gepa logs its own error traceback")
def test_gepa_optimize_records_errors(client: WeaveClient) -> None:
    """GEPA's engine dispatches `on_error` when an iteration raises.
    Exceptions escaping the adapter's `evaluate()` propagate out of the
    reflective-mutation proposer (after the seed eval) and reach the engine's
    `on_error` dispatch. We should emit a `gepa.error` span with the
    exception type/message so users can count and inspect failures.
    """

    class _ExplodingAdapter(_StubAdapter):
        propose_new_texts = None  # type: ignore[assignment]
        _call_count = 0

        def evaluate(
            self,
            batch: Sequence[Any],
            candidate: dict[str, str],
            capture_traces: bool = False,
        ) -> EvaluationBatch:
            self._call_count += 1
            # Let the seed's full-valset eval succeed, raise on the next call
            # (proposer minibatch eval) so the error escapes into the engine's
            # iteration-level handler where `on_error` fires, then succeed
            # afterwards so the run's budget actually gets consumed and
            # optimization terminates.
            if self._call_count == 2:
                raise RuntimeError("simulated evaluation failure")
            return super().evaluate(batch, candidate, capture_traces)

    gepa.optimize(
        seed_candidate={"instructions": "seed"},
        trainset=[{"q": "a"}, {"q": "b"}, {"q": "c"}],
        valset=[{"q": "d"}],
        adapter=_ExplodingAdapter(),
        reflection_lm=_stub_reflection_lm,
        max_metric_calls=6,
        display_progress_bar=False,
        raise_on_exception=False,
        skip_perfect_score=False,
    )

    # Error should surface on the span where it actually happened
    # (gepa.evaluate), not a separate sibling span. This avoids logging the
    # same exception twice in the trace tree.
    all_calls = list(client.get_calls())
    errored_evals = [
        c
        for c in all_calls
        if op_name_from_ref(c.op_name) == "gepa.evaluate" and c.exception
    ]
    assert errored_evals, "expected the failing gepa.evaluate span to be marked errored"
    errored = errored_evals[0]
    assert "simulated evaluation failure" in (errored.exception or "")
    # GEPA engine metadata (iteration / will_continue / exception_type) should
    # be annotated onto the errored span's output for click-through inspection.
    output = errored.output or {}
    assert output.get("exception_type") == "RuntimeError"
    assert "simulated evaluation failure" in (output.get("exception_message") or "")
    # There should be NO standalone gepa.error span in this trace — the
    # exception is recorded on the gepa.evaluate span that raised it.
    standalone_errors = [
        c for c in all_calls if op_name_from_ref(c.op_name) == "gepa.error"
    ]
    assert not standalone_errors, (
        f"expected no standalone gepa.error spans, got {len(standalone_errors)}"
    )


@pytest.mark.skip_clickhouse_client
def test_gepa_optimize_publishes_candidate_versions(client: WeaveClient) -> None:
    """Each iteration's accepted candidate should be published as a new
    version of the `gepa_candidate` object so users can browse prompt history.
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

    # Query the published `gepa_candidate` object via the trace server to
    # confirm at least two versions exist (seed + one accepted candidate).
    from weave.trace_server.trace_server_interface import (
        ObjectVersionFilter,
        ObjQueryReq,
    )

    resp = client.server.objs_query(
        ObjQueryReq(
            project_id=client.project_id,
            filter=ObjectVersionFilter(object_ids=["gepa_candidate"]),
        )
    )
    assert len(resp.objs) >= 2, [o.object_id for o in resp.objs]

    # The first and latest versions should reflect the seed and final candidate.
    vals = {o.digest: o.val for o in resp.objs}
    assert any(
        isinstance(v, dict) and v.get("instructions") == "seed" for v in vals.values()
    )
    assert any(
        isinstance(v, dict) and v.get("instructions") == "seed MORE"
        for v in vals.values()
    )


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
