"""Benchmark for eval_results_query overhead from the score-merge change.

Runs against either backend via the standard trace_server fixture:
    nox --no-install -e "tests-3.12(shard='trace_server')" -- \\
        tests/trace_server/bench_eval_results_query.py \\
        --trace-server=sqlite -p no:xdist --no-cov -s

To exercise ClickHouse, swap to --trace-server=clickhouse --clickhouse-process=true.

A/B comparison: setup happens once per case. We then time eval_results_query
twice — once with the patched merge active, once with the merge stubbed out
to a pass-through (the baseline behavior). This shares setup costs and removes
between-run noise.

Note: filename starts with ``bench_`` (not ``test_``) so it is opt-in — pytest
won't collect it from a regular shard run. Pass the path explicitly to run.
"""

from __future__ import annotations

import base64
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from weave.trace_server import eval_results_helpers
from weave.trace_server import trace_server_interface as tsi


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("ascii")).decode("ascii")


def setup_eval(
    server,
    project_id: str,
    num_preds: int,
    num_scores_each: int,
) -> str:
    scorer_refs: list[str] = []
    for i in range(num_scores_each):
        res = server.scorer_create(
            tsi.ScorerCreateReq(
                project_id=project_id,
                name=f"scorer_{i}",
                op_source_code="def score(output):\n    return 1.0\n",
            )
        )
        scorer_refs.append(
            f"weave-trace-internal:///{project_id}/object/{res.object_id}:{res.digest}"
        )

    run = server.evaluation_run_create(
        tsi.EvaluationRunCreateReq(
            project_id=project_id,
            evaluation="eval://bench",
            model="model://bench",
        )
    )
    run_id = run.evaluation_run_id

    for p in range(num_preds):
        pred = server.prediction_create(
            tsi.PredictionCreateReq(
                project_id=project_id,
                model="model://bench",
                inputs={"x": p},
                output=f"result_{p}",
                evaluation_run_id=run_id,
            )
        )
        for s in range(num_scores_each):
            server.score_create(
                tsi.ScoreCreateReq(
                    project_id=project_id,
                    prediction_id=pred.prediction_id,
                    scorer=scorer_refs[s],
                    value=0.5,
                    evaluation_run_id=run_id,
                )
            )
        server.prediction_finish(
            tsi.PredictionFinishReq(
                project_id=project_id,
                prediction_id=pred.prediction_id,
            )
        )

    return run_id


def time_query(
    server, project_id: str, eval_run_id: str, iters: int
) -> tuple[float, float, float]:
    times: list[float] = []
    for _ in range(iters):
        t0 = time.perf_counter()
        server.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[eval_run_id],
                include_summary=True,
            )
        )
        times.append(time.perf_counter() - t0)
    return min(times), sum(times) / len(times), max(times)


def _baseline_merge(scores: dict[str, Any], trial_children: list) -> dict[str, Any]:
    """Stand-in for the pre-change behavior: just return the scores as-is."""
    return dict(scores) if isinstance(scores, dict) else {}


@contextmanager
def baseline_merge_active() -> Iterator[None]:
    original = eval_results_helpers._merge_scores_from_child_calls
    eval_results_helpers._merge_scores_from_child_calls = _baseline_merge
    try:
        yield
    finally:
        eval_results_helpers._merge_scores_from_child_calls = original


CASES = [
    (10, 10),
    (10, 100),
    (100, 10),
    (100, 100),
    (1000, 10),
    (1000, 100),
]


@pytest.mark.parametrize("num_preds,num_scores", CASES)
def test_bench(trace_server, num_preds, num_scores):
    """A/B benchmark: time eval_results_query with and without the merge."""
    inner = trace_server._internal_trace_server
    project_id = _b64(f"bench_{num_preds}x{num_scores}")
    t_setup0 = time.perf_counter()
    eval_id = setup_eval(inner, project_id, num_preds, num_scores)
    t_setup = time.perf_counter() - t_setup0
    iters = 5 if num_preds * num_scores < 50_000 else 3

    # warmup
    inner.eval_results_query(
        tsi.EvalResultsQueryReq(
            project_id=project_id,
            evaluation_call_ids=[eval_id],
            include_summary=True,
        )
    )

    # interleave to share any drift in load
    base_times: list[float] = []
    patch_times: list[float] = []
    for _ in range(iters):
        with baseline_merge_active():
            t0 = time.perf_counter()
            inner.eval_results_query(
                tsi.EvalResultsQueryReq(
                    project_id=project_id,
                    evaluation_call_ids=[eval_id],
                    include_summary=True,
                )
            )
            base_times.append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        inner.eval_results_query(
            tsi.EvalResultsQueryReq(
                project_id=project_id,
                evaluation_call_ids=[eval_id],
                include_summary=True,
            )
        )
        patch_times.append(time.perf_counter() - t0)

    def stats(ts: list[float]) -> tuple[float, float]:
        return min(ts) * 1000, sum(ts) / len(ts) * 1000

    bmin, bmean = stats(base_times)
    pmin, pmean = stats(patch_times)
    delta_min_pct = (pmin - bmin) / bmin * 100
    delta_mean_pct = (pmean - bmean) / bmean * 100

    print(
        f"\nBENCH preds={num_preds:>5} scores={num_scores:>4} "
        f"base min/mean = {bmin:>8.2f}/{bmean:>8.2f}ms "
        f"patched min/mean = {pmin:>8.2f}/{pmean:>8.2f}ms "
        f"Δ min={delta_min_pct:+5.1f}% mean={delta_mean_pct:+5.1f}% "
        f"(setup {t_setup:.1f}s, n={iters})"
    )
