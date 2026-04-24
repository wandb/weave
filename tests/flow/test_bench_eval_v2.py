"""Benchmark: EvaluationLoggerV2 vs V1 under simulated remote-backend RTT.

Each server round-trip is given a ``time.sleep(0.02)`` shim to emulate a
50 ms RTT backend. V2 now parallelizes its V2-endpoint round-trips
(`prediction_create`, `score_create`, `prediction_finish`) through a
ThreadPoolExecutor, so user code should not block on the network and the
total wall-clock should stay close to V1 even though V2 issues more
distinct round-trips per prediction.

Run with::

    pytest tests/flow/test_bench_eval_v2.py -v -s
"""

from __future__ import annotations

import time
from typing import Any

from weave.evaluation.eval_imperative import EvaluationLogger as EvaluationLoggerV1
from weave.evaluation.eval_imperative_v2 import EvaluationLoggerV2

RTT_SECONDS = 0.02
NUM_PREDICTIONS = 20
NUM_SCORERS = 3


def _install_rtt_shim(
    server: Any, methods: tuple[str, ...], delay: float = RTT_SECONDS
) -> list[tuple[str, Any]]:
    """Wrap each ``server.<method>`` to sleep ``delay`` before dispatching.

    Returns the original callables so the caller can restore them after
    the benchmark — isolating the shim to a single benchmark region.
    """
    originals: list[tuple[str, Any]] = []
    for name in methods:
        original = getattr(server, name)
        originals.append((name, original))

        def _make_wrapper(orig: Any) -> Any:
            def _wrapper(*args: Any, **kwargs: Any) -> Any:
                time.sleep(delay)
                return orig(*args, **kwargs)

            return _wrapper

        setattr(server, name, _make_wrapper(original))
    return originals


def _restore(server: Any, originals: list[tuple[str, Any]]) -> None:
    for name, orig in originals:
        setattr(server, name, orig)


def _run_v2(client) -> tuple[float, float]:
    """Drive V2 and return (user_code_elapsed, total_elapsed) in seconds."""
    originals = _install_rtt_shim(
        client.server,
        ("prediction_create", "score_create", "prediction_finish"),
    )
    try:
        start = time.perf_counter()
        ev = EvaluationLoggerV2(
            name="bench_v2",
            model="bench_model_v2",
            dataset=[{"i": i} for i in range(NUM_PREDICTIONS)],
        )
        for i in range(NUM_PREDICTIONS):
            pred = ev.log_prediction(inputs={"i": i}, output=f"out-{i}")
            for s in range(NUM_SCORERS):
                pred.log_score(f"scorer_{s}", 0.5 + s * 0.1)
            pred.finish()
        user_code_elapsed = time.perf_counter() - start

        ev.log_summary({"ok": True})
        total_elapsed = time.perf_counter() - start
    finally:
        _restore(client.server, originals)
    return user_code_elapsed, total_elapsed


def _run_v1(client) -> tuple[float, float]:
    """Drive V1 and return (user_code_elapsed, total_elapsed) in seconds.

    V1 flushes through ``call_start``/``call_end`` — its rough per-server
    analogue of V2's prediction/score endpoints. We shim both so the RTT
    cost model is comparable.
    """
    originals = _install_rtt_shim(
        client.server,
        ("call_start", "call_end"),
    )
    try:
        start = time.perf_counter()
        ev = EvaluationLoggerV1(
            name="bench_v1",
            model="bench_model_v1",
            dataset=[{"i": i} for i in range(NUM_PREDICTIONS)],
        )
        for i in range(NUM_PREDICTIONS):
            pred = ev.log_prediction(inputs={"i": i}, output=f"out-{i}")
            for s in range(NUM_SCORERS):
                pred.log_score(f"scorer_{s}", 0.5 + s * 0.1)
            pred.finish()
        user_code_elapsed = time.perf_counter() - start

        ev.log_summary({"ok": True})
        total_elapsed = time.perf_counter() - start
    finally:
        _restore(client.server, originals)
    return user_code_elapsed, total_elapsed


def test_bench_v2_is_not_slower_than_v1(client):
    """V2 must not be meaningfully slower than V1 under simulated RTT.

    Asserts:
      * V2 user-code < 500 ms (user code never blocks on the network).
      * V2 total     < 4 s   (parallel HTTP drains quickly).
      * V2 total     < V1 total * 1.2 (V2 on par with V1).
    """
    # Warm-up: the first eval pays a one-time module/integration init cost
    # (imports, patching) that would bias whichever logger runs first.
    _run_v2(client)
    _run_v1(client)

    v1_user, v1_total = _run_v1(client)
    v2_user, v2_total = _run_v2(client)

    print("\n=== EvaluationLogger benchmark (20 predictions x 3 scorers) ===")
    print(f"RTT shim:              {RTT_SECONDS * 1000:.0f} ms per call")
    print(f"V1 user-code elapsed:  {v1_user * 1000:8.1f} ms")
    print(f"V1 total elapsed:      {v1_total * 1000:8.1f} ms")
    print(f"V2 user-code elapsed:  {v2_user * 1000:8.1f} ms")
    print(f"V2 total elapsed:      {v2_total * 1000:8.1f} ms")
    ratio = v2_total / v1_total if v1_total > 0 else float("inf")
    print(f"V2/V1 total ratio:     {ratio:.2f}x")

    assert v2_user < 0.5, (
        f"V2 user-code should not block on network; got {v2_user * 1000:.1f} ms"
    )
    assert v2_total < 4.0, (
        f"V2 total should drain in parallel; got {v2_total * 1000:.1f} ms"
    )
    assert v2_total < v1_total * 1.2, (
        "V2 must not be meaningfully slower than V1: "
        f"V2={v2_total * 1000:.1f} ms, V1={v1_total * 1000:.1f} ms, "
        f"ratio={ratio:.2f}x"
    )
