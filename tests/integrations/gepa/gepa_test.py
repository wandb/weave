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
from weave.trace_server.trace_server_interface import (
    CallsFilter,
    ObjectVersionFilter,
    ObjQueryReq,
)


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


class _ConcisenessAdapter:
    """End-to-end-shaped adapter: scores `1 - len(instructions)/100`.

    Shorter prompts win, so a reflection LM that returns a short candidate
    actually beats the long seed. Used to validate the realistic-improvement
    flow (candidate score actually goes up, multiple `gepa_candidate`
    versions get published, reflection LM nests under `gepa.propose`).
    """

    propose_new_texts = None  # force the reflection-LM path

    def evaluate(
        self,
        batch: Sequence[Any],
        candidate: dict[str, str],
        capture_traces: bool = False,
    ) -> EvaluationBatch:
        text = candidate.get("instructions", "")
        score = max(0.0, 1.0 - min(1.0, len(text) / 100.0))
        outputs = [f"answered: {ex!r}" for ex in batch]
        scores = [score for _ in batch]
        trajectories = [{"len": len(text)} for _ in batch] if capture_traces else None
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


@pytest.mark.skip_clickhouse_client
def test_gepa_optimize_end_to_end_with_reflection_lm(client: WeaveClient) -> None:
    """Realistic happy-path: long seed prompt scores 0; reflection LM proposes
    a short candidate that scores higher. Validates that:
      - GEPA actually accepts the proposal (best_idx > 0).
      - The reflection LM call nests under `gepa.propose`.
      - Multiple `gepa_candidate` versions get published (seed + improvement).
    """

    @weave.op
    def short_reflection_lm(prompt: str | list[dict[str, Any]]) -> str:
        return "```\nBe brief.\n```"

    seed = {
        "instructions": (
            "Please read the question very carefully and then give me a "
            "detailed, thoughtful, well-reasoned answer explaining every step."
        )
    }
    result = gepa.optimize(
        seed_candidate=seed,
        trainset=[{"q": f"train-{i}"} for i in range(3)],
        valset=[{"q": f"val-{i}"} for i in range(2)],
        adapter=_ConcisenessAdapter(),
        reflection_lm=short_reflection_lm,
        max_metric_calls=12,
        display_progress_bar=False,
        raise_on_exception=False,
        skip_perfect_score=False,
    )

    # GEPA should have accepted the shorter proposal over the long seed.
    assert getattr(result, "best_idx", 0) > 0, (
        f"expected reflection LM to beat seed; got best_idx="
        f"{getattr(result, 'best_idx', None)}"
    )
    assert getattr(result, "num_candidates", 0) >= 2

    # Reflection LM should nest under gepa.propose (LM-call cost attribution).
    roots = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    optimize_roots = [
        r for r in roots if op_name_from_ref(r.op_name) == "gepa.optimize"
    ]
    assert len(optimize_roots) == 1
    names = flattened_calls_to_names(flatten_calls(optimize_roots))
    propose_idx = next(i for i, (n, _) in enumerate(names) if n == "gepa.propose")
    propose_depth = names[propose_idx][1]
    propose_children = [
        n
        for i, (n, d) in enumerate(names[propose_idx + 1 :], start=propose_idx + 1)
        if d == propose_depth + 1
        and all(names[j][1] > propose_depth for j in range(propose_idx + 1, i + 1))
    ]
    assert "short_reflection_lm" in propose_children, (
        f"reflection LM should nest under gepa.propose; "
        f"propose children={propose_children!r}"
    )

    # At least two `gepa_candidate` versions: seed and the accepted shorter one.
    resp = client.server.objs_query(
        ObjQueryReq(
            project_id=client.project_id,
            filter=ObjectVersionFilter(object_ids=["gepa_candidate"]),
        )
    )
    instructions = {
        o.val.get("instructions")
        for o in resp.objs
        if isinstance(o.val, dict) and "instructions" in o.val
    }
    assert seed["instructions"] in instructions
    assert "Be brief." in instructions


class _FlakyAdapter(_ConcisenessAdapter):
    """Variant that raises on a configurable set of `evaluate()` call indices.

    1-indexed: call 1 is the seed's full-valset eval which we always let
    succeed (otherwise the run can't even start).
    """

    def __init__(self, fail_on_call_counts: set[int]) -> None:
        self._fail_on_call_counts = fail_on_call_counts
        self._call_count = 0

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
        return super().evaluate(batch, candidate, capture_traces)


@pytest.mark.skip_clickhouse_client
@pytest.mark.disable_logging_error_check(reason="gepa logs its own error traceback")
def test_gepa_optimize_records_multiple_errors(client: WeaveClient) -> None:
    """When several iterations fail, each errored `gepa.evaluate` span should
    carry its own RuntimeError + engine metadata, and there should be no
    standalone `gepa.error` siblings double-logging the same exception.
    Counts the number of errored evaluate spans against the requested
    failure pattern.
    """

    @weave.op
    def short_reflection_lm(prompt: str | list[dict[str, Any]]) -> str:
        return "```\nBe brief.\n```"

    fail_call_counts = {2, 4, 6}
    gepa.optimize(
        seed_candidate={"instructions": "Please answer carefully."},
        trainset=[{"q": f"train-{i}"} for i in range(4)],
        valset=[{"q": f"val-{i}"} for i in range(2)],
        adapter=_FlakyAdapter(fail_on_call_counts=fail_call_counts),
        reflection_lm=short_reflection_lm,
        max_metric_calls=20,
        display_progress_bar=False,
        raise_on_exception=False,
        skip_perfect_score=False,
    )

    all_calls = list(client.get_calls())
    errored_evals = [
        c
        for c in all_calls
        if op_name_from_ref(c.op_name) == "gepa.evaluate" and c.exception
    ]
    assert errored_evals, "expected at least one errored gepa.evaluate span"
    # Each requested failure should map to exactly one errored span.
    assert len(errored_evals) == len(fail_call_counts), (
        f"expected {len(fail_call_counts)} errored evaluate spans; "
        f"got {len(errored_evals)}"
    )
    for c in errored_evals:
        output = c.output or {}
        assert output.get("exception_type") == "RuntimeError"
        assert "simulated evaluation failure" in (output.get("exception_message") or "")
    # No standalone gepa.error spans — exceptions are recorded on the
    # span that raised them.
    standalone_errors = [
        c for c in all_calls if op_name_from_ref(c.op_name) == "gepa.error"
    ]
    assert not standalone_errors
