"""Benchmark obj_create against a remote weave-trace server.

Designed to stress the patterns we hit during evaluations, where the
weave_client publishes many objects in parallel via a thread pool. Captures
per-call latency and reports p50/p95/p99/max + throughput so we can compare
before/after a backend change.

The `concurrent name+type collision` scenario specifically exercises the
TOCTOU window in the WB-30574 collision check: many threads race to create
the same object_id under alternating base_object_class values. The check is
a SELECT-then-INSERT with no transaction in ClickHouse, so two concurrent
creates can both pass the check and both land — leaving the table in the
exact corrupt state the PR is meant to prevent. This scenario surfaces
that with a post-run integrity assertion (distinct base_object_class for
the contested name) plus rejected-create counts.

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
    # Optional integrity field for scenarios that care about post-run server state.
    integrity_note: str | None = None

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
    api_key = os.environ["WANDB_API_KEY"]
    server = RemoteHTTPTraceServer.from_env(should_batch=False)
    server.set_auth(("api", api_key))
    return server


def make_unique_val(tag: str) -> dict:
    """Return a payload whose digest is guaranteed unique.

    obj_create short-circuits when (project_id, object_id, digest) already
    exists, so we sprinkle a uuid into every val to keep every create writing.
    """
    return {"tag": tag, "nonce": str(uuid.uuid4()), "payload": "x" * 64}


def make_typed_val(class_name: str, tag: str) -> dict:
    """Return a payload that resolves to base_object_class=class_name server-side.

    `process_incoming_object_val` takes the first branch when `_bases` ends in
    [<Object|BaseObject>, BaseModel], using `_class_name` verbatim — no
    registry lookup, no schema validation. That's exactly what the collision
    scenario needs: pick any two distinct class names and they'll land with
    differing base_object_class.
    """
    return {
        "_class_name": class_name,
        "_bases": ["Object", "BaseModel"],
        "tag": tag,
        "nonce": str(uuid.uuid4()),
    }


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


def make_create_worker(
    server: RemoteHTTPTraceServer,
    project_id: str,
    object_id: str,
    val: dict,
    builtin_object_class: str | None = None,
) -> Callable[[], float]:
    """Bind one `timed_create` call into a zero-arg worker for `run_scenario`."""
    return lambda: timed_create(
        server, project_id, object_id, val, builtin_object_class
    )


def run_scenario(
    name: str,
    *,
    workers: list[Callable[[], float]],
    threads: int,
    expected_error_substring: str | None = None,
) -> ScenarioResult:
    """Run a scenario and collect per-call latencies.

    If `expected_error_substring` is set, exceptions whose str contains that
    substring count toward `errors` but are not printed — they're the
    designed-rejection path for collision scenarios.
    """
    print(f"  running {name!r} (n={len(workers)}, threads={threads})...", flush=True)
    latencies: list[float] = []
    errors = 0

    def consume(future_result_fn: Callable[[], float]) -> None:
        nonlocal errors
        try:
            latencies.append(future_result_fn())
        except Exception as e:
            errors += 1
            msg = str(e)
            if not expected_error_substring or expected_error_substring not in msg:
                print(f"    error: {e}", flush=True)

    start = time.perf_counter()
    if threads == 1:
        for w in workers:
            consume(w)
    else:
        with ThreadPoolExecutor(max_workers=threads) as pool:
            futures = [pool.submit(w) for w in workers]
            for f in futures:
                consume(f.result)
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
        make_create_worker(
            server, project_id, f"seq_{run_id}_{i}", make_unique_val(f"seq_{i}")
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
        make_create_worker(
            server, project_id, f"par_{run_id}_{i}", make_unique_val(f"par_{i}")
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
    of existing versions of this object_id.
    """
    name = f"versioned_{run_id}"
    workers = [
        make_create_worker(server, project_id, name, make_unique_val(f"v{i}"))
        for i in range(n)
    ]
    return run_scenario(
        f"versions of one name x{threads}", workers=workers, threads=threads
    )


def scenario_concurrent_name_type_collision(
    server: RemoteHTTPTraceServer,
    project_id: str,
    run_id: str,
    n: int,
    threads: int,
) -> ScenarioResult:
    """Race many concurrent obj_create calls against the same object_id, with
    threads alternating between two distinct base_object_class values.

    Expected outcome under a correct implementation:
        - exactly one base_object_class "wins" (whichever insert lands first)
        - all subsequent creates with the other class are rejected with
          ObjectNameTypeCollision
        - the table ends up with exactly one distinct base_object_class

    Under TOCTOU, two concurrent SELECT queries both see an empty result, both pass
    the check, and the table ends up with two distinct base_object_class
    values for the same name. That state is exactly what WB-30574 is meant
    to prevent and we detect it via a post-run objs_query.
    """
    name = f"collide_{run_id}"
    class_a = "BenchClassA"
    class_b = "BenchClassB"
    workers = [
        make_create_worker(
            server,
            project_id,
            name,
            make_typed_val(class_a if i % 2 == 0 else class_b, f"v{i}"),
        )
        for i in range(n)
    ]
    result = run_scenario(
        f"name+type collision x{threads}",
        workers=workers,
        threads=threads,
        expected_error_substring="ObjectNameTypeCollision",
    )

    # Post-run integrity: how many distinct base_object_class values landed for
    # this name? >1 means the TOCTOU window opened and the invariant was
    # violated. Includes a small sleep to let ReplacingMergeTree merges settle
    # (results still reflect raw rows under DISTINCT either way).
    time.sleep(1.0)
    objs_res = server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": project_id,
                "filter": {"object_ids": [name]},
            }
        )
    )
    distinct_classes = sorted(
        {o.base_object_class for o in objs_res.objs if o.base_object_class is not None}
    )
    result.integrity_note = (
        f"distinct base_object_class for {name!r}: {distinct_classes} "
        f"(versions={len(objs_res.objs)}, expected: 1 distinct class)"
    )
    return result


def scenario_eval_like(
    server: RemoteHTTPTraceServer,
    project_id: str,
    run_id: str,
    n_outputs: int,
    threads: int,
) -> ScenarioResult:
    """Closest to a real evaluation: a few typed publishes + many unique
    untyped outputs, all racing through a thread pool.
    """
    # A handful of typed singletons (dataset, model, scorer) up front.
    workers: list[Callable[[], float]] = [
        make_create_worker(
            server, project_id, f"eval_dataset_{run_id}", make_unique_val("dataset")
        ),
        make_create_worker(
            server, project_id, f"eval_model_{run_id}", make_unique_val("model")
        ),
        make_create_worker(
            server, project_id, f"eval_scorer_{run_id}", make_unique_val("scorer")
        ),
    ]
    for i in range(n_outputs):
        workers.append(
            make_create_worker(
                server,
                project_id,
                f"eval_output_{run_id}_{i}",
                make_unique_val(f"output_{i}"),
            )
        )
    return run_scenario(f"eval-like x{threads}", workers=workers, threads=threads)


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
        "--n-collision",
        type=int,
        default=100,
        help="Concurrent creates for the name+type collision scenario",
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
        scenario_concurrent_name_type_collision(
            server, project_id, run_id, n=args.n_collision, threads=args.threads
        )
    )
    results.append(
        scenario_eval_like(
            server,
            project_id,
            run_id,
            n_outputs=args.n_eval_outputs,
            threads=args.threads,
        )
    )

    print()
    print(format_table(results))

    integrity_notes = [r.integrity_note for r in results if r.integrity_note]
    if integrity_notes:
        print()
        print("Integrity checks:")
        for note in integrity_notes:
            print(f"  {note}")


if __name__ == "__main__":
    main()
