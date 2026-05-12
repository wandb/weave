"""Benchmark obj_create against a remote weave-trace server.

Designed to stress the patterns we hit during evaluations, where the
weave_client publishes many objects in parallel via a thread pool. Captures
per-call latency and reports p50/p95/p99/max + throughput so we can compare
before/after a backend change.

Usage:
    qa  # source the qa env aliased in ~/.zshrc
    uv run --group test python scripts/benchmarks/obj_create_bench.py

Env vars consumed: WF_TRACE_SERVER_URL, WANDB_API_KEY, WANDB_ENTITY.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import statistics
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
)


@dataclasses.dataclass
class ScenarioResult:
    name: str
    total_calls: int
    threads: int
    wall_seconds: float
    per_call_ms: list[float]
    errors: int

    @property
    def throughput(self) -> float:
        return self.total_calls / self.wall_seconds if self.wall_seconds else 0.0

    def quantile(self, q: float) -> float:
        if not self.per_call_ms:
            return float("nan")
        return statistics.quantiles(self.per_call_ms, n=100, method="inclusive")[
            int(q * 100) - 1
        ]


def build_server() -> RemoteHTTPTraceServer:
    url = os.environ["WF_TRACE_SERVER_URL"]
    api_key = os.environ["WANDB_API_KEY"]
    server = RemoteHTTPTraceServer(url, should_batch=False)
    server.set_auth(("api", api_key))
    return server


def make_unique_val(tag: str) -> dict:
    """Return a payload whose digest is guaranteed unique.

    obj_create short-circuits when (project_id, object_id, digest) already
    exists, so we sprinkle a uuid into every val to keep every create writing.
    """
    return {"tag": tag, "nonce": str(uuid.uuid4()), "payload": "x" * 64}


def timed_create(
    server: RemoteHTTPTraceServer,
    project_id: str,
    object_id: str,
    val: dict,
    builtin_object_class: str | None = None,
) -> float:
    req = tsi.ObjCreateReq.model_validate(
        {
            "obj": {
                "project_id": project_id,
                "object_id": object_id,
                "val": val,
                **(
                    {"builtin_object_class": builtin_object_class}
                    if builtin_object_class
                    else {}
                ),
            }
        }
    )
    start = time.perf_counter()
    server.obj_create(req)
    return (time.perf_counter() - start) * 1000.0


def run_scenario(
    name: str,
    *,
    workers: list[Callable[[], float]],
    threads: int,
) -> ScenarioResult:
    print(f"  running {name!r} (n={len(workers)}, threads={threads})...", flush=True)
    latencies: list[float] = []
    errors = 0

    start = time.perf_counter()
    if threads == 1:
        for w in workers:
            try:
                latencies.append(w())
            except Exception as e:  # noqa: BLE001 - benchmark, surface count
                errors += 1
                print(f"    error: {e}", flush=True)
    else:
        with ThreadPoolExecutor(max_workers=threads) as pool:
            futures = [pool.submit(w) for w in workers]
            for f in futures:
                try:
                    latencies.append(f.result())
                except Exception as e:  # noqa: BLE001
                    errors += 1
                    print(f"    error: {e}", flush=True)
    wall = time.perf_counter() - start

    return ScenarioResult(
        name=name,
        total_calls=len(workers),
        threads=threads,
        wall_seconds=wall,
        per_call_ms=latencies,
        errors=errors,
    )


def scenario_sequential_unique(
    server: RemoteHTTPTraceServer, project_id: str, run_id: str, n: int
) -> ScenarioResult:
    workers = [
        (
            lambda i=i: timed_create(
                server,
                project_id,
                object_id=f"seq_{run_id}_{i}",
                val=make_unique_val(f"seq_{i}"),
            )
        )
        for i in range(n)
    ]
    return run_scenario("sequential unique", workers=workers, threads=1)


def scenario_concurrent_unique(
    server: RemoteHTTPTraceServer,
    project_id: str,
    run_id: str,
    n: int,
    threads: int,
) -> ScenarioResult:
    workers = [
        (
            lambda i=i: timed_create(
                server,
                project_id,
                object_id=f"par_{run_id}_{i}",
                val=make_unique_val(f"par_{i}"),
            )
        )
        for i in range(n)
    ]
    return run_scenario(
        f"concurrent unique x{threads}", workers=workers, threads=threads
    )


def scenario_concurrent_versions_one_name(
    server: RemoteHTTPTraceServer,
    project_id: str,
    run_id: str,
    n: int,
    threads: int,
) -> ScenarioResult:
    """Stress the new collision-check path: every create scans the growing set
    of existing versions of this object_id."""
    name = f"versioned_{run_id}"
    workers = [
        (
            lambda i=i: timed_create(
                server,
                project_id,
                object_id=name,
                val=make_unique_val(f"v{i}"),
            )
        )
        for i in range(n)
    ]
    return run_scenario(
        f"versions of one name x{threads}", workers=workers, threads=threads
    )


def scenario_eval_like(
    server: RemoteHTTPTraceServer,
    project_id: str,
    run_id: str,
    n_outputs: int,
    threads: int,
) -> ScenarioResult:
    """Closest to a real evaluation: a few typed publishes + many unique
    untyped outputs, all racing through a thread pool."""
    workers: list[Callable[[], float]] = []

    # A handful of typed singletons (dataset, model, scorer) up front.
    workers.append(
        lambda: timed_create(
            server,
            project_id,
            object_id=f"eval_dataset_{run_id}",
            val=make_unique_val("dataset"),
        )
    )
    workers.append(
        lambda: timed_create(
            server,
            project_id,
            object_id=f"eval_model_{run_id}",
            val=make_unique_val("model"),
        )
    )
    workers.append(
        lambda: timed_create(
            server,
            project_id,
            object_id=f"eval_scorer_{run_id}",
            val=make_unique_val("scorer"),
        )
    )
    for i in range(n_outputs):
        workers.append(
            lambda i=i: timed_create(
                server,
                project_id,
                object_id=f"eval_output_{run_id}_{i}",
                val=make_unique_val(f"output_{i}"),
            )
        )
    return run_scenario(
        f"eval-like x{threads}", workers=workers, threads=threads
    )


def format_table(results: list[ScenarioResult]) -> str:
    rows = [
        (
            "scenario",
            "n",
            "threads",
            "wall(s)",
            "thr/s",
            "p50(ms)",
            "p95(ms)",
            "p99(ms)",
            "max(ms)",
            "err",
        )
    ]
    for r in results:
        rows.append(
            (
                r.name,
                str(r.total_calls),
                str(r.threads),
                f"{r.wall_seconds:.2f}",
                f"{r.throughput:.1f}",
                f"{r.quantile(0.50):.1f}",
                f"{r.quantile(0.95):.1f}",
                f"{r.quantile(0.99):.1f}",
                f"{max(r.per_call_ms):.1f}" if r.per_call_ms else "-",
                str(r.errors),
            )
        )
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    lines = []
    for idx, row in enumerate(rows):
        line = "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
        lines.append(line)
        if idx == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--entity",
        default=os.environ.get("WANDB_ENTITY", "griffin"),
    )
    parser.add_argument("--project", default="weave-obj-create-bench")
    parser.add_argument(
        "--threads", type=int, default=8, help="Concurrency for parallel scenarios"
    )
    parser.add_argument(
        "--n-sequential", type=int, default=30, help="Calls in sequential scenario"
    )
    parser.add_argument(
        "--n-parallel-unique",
        type=int,
        default=150,
        help="Calls in concurrent-unique scenario",
    )
    parser.add_argument(
        "--n-versions",
        type=int,
        default=100,
        help="Versions for the one-name scenario",
    )
    parser.add_argument(
        "--n-eval-outputs",
        type=int,
        default=100,
        help="Output objects in the eval-like scenario",
    )
    args = parser.parse_args()

    project_id = f"{args.entity}/{args.project}"
    server = build_server()
    print(f"trace server: {os.environ['WF_TRACE_SERVER_URL']}")
    print(f"project:      {project_id}")
    server.ensure_project_exists(args.entity, args.project)

    # Each invocation of the script gets its own object_id namespace so runs
    # don't poison each other. We also deliberately don't clean up — repeated
    # runs accumulate, which is itself useful signal on the check's cost.
    run_id = uuid.uuid4().hex[:8]
    print(f"run_id:       {run_id}")
    print()

    results: list[ScenarioResult] = []
    results.append(
        scenario_sequential_unique(server, project_id, run_id, n=args.n_sequential)
    )
    results.append(
        scenario_concurrent_unique(
            server, project_id, run_id, n=args.n_parallel_unique, threads=args.threads
        )
    )
    results.append(
        scenario_concurrent_versions_one_name(
            server, project_id, run_id, n=args.n_versions, threads=args.threads
        )
    )
    results.append(
        scenario_eval_like(
            server, project_id, run_id, n_outputs=args.n_eval_outputs, threads=args.threads
        )
    )

    print()
    print(format_table(results))


if __name__ == "__main__":
    main()
