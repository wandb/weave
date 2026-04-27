"""Load test for ExternalTraceServer deep-copy overhead (PR #6670).

Background: #6670 adds `req = req.model_copy(deep=True)` at the top of every
public adapter method to fix the project_id mutation bug. Andrew flagged
perf concern: pydantic deep-copy walks the full model and copies every
value, so large requests (big call inputs, many-row tables, large obj
vals) pay for it on every adapter call.

This script exercises the adapter paths with payloads sized to surface
that cost. Run twice — once against an image with master, once with the
#6670 image deployed to QA — and compare per-scenario p50/p95/p99/max.

Scenarios (in order of expected sensitivity to deep-copy):
  small_tight          baseline: trivial op, tight loop. deep-copy is a
                       bigger fraction of per-request cost here.
  wide_dict_input      op takes a 1000-key dict → adapter deep-copies
                       1000 leaves per call.
  deep_nested_input    op takes a 50-level nested dict → recursion depth.
  long_string_input    op takes a 1MB string input + output.
  many_refs_input      op takes a dict of 500 ref URIs (common eval shape).
  dataset_publish      weave.publish(Dataset(rows=[...])) — stresses
                       table_create (N rows) and obj_create (embeds ref).
  table_create_direct  client.server.table_create directly, bypassing
                       tracing. Isolates the adapter cost from op overhead.

Example usage:
    # Point weave at QA first: export WANDB_BASE_URL=https://api.qa.wandb.ai
    python weave_large_payloads.py --project perf-6670-before -i 500
    # Switch to the 6670 image on QA, re-run:
    python weave_large_payloads.py --project perf-6670-after  -i 500
    # Diff the printed summary tables.

Focus on p95/p99 and max — deep-copy cost is most visible in the tail
for large payloads, and in the median for the small_tight scenario.
"""

from __future__ import annotations

import argparse
import statistics
import string
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi

SMALL_TIGHT_ITERATIONS = 500
WIDE_DICT_KEYS = 1000
DEEP_NEST_LEVELS = 50
LONG_STRING_BYTES = 1_000_000  # 1 MB
MANY_REFS_COUNT = 500
DATASET_ROW_COUNTS = (100, 1000, 10_000)
TABLE_ROW_COUNTS = (100, 1000, 10_000)


@dataclass
class ScenarioResult:
    name: str
    payload_desc: str
    iterations: int
    times_ms: list[float] = field(default_factory=list)

    def summary(self) -> dict[str, float]:
        t = sorted(self.times_ms)
        n = len(t)
        if n == 0:
            return {}
        return {
            "n": n,
            "min": t[0],
            "p50": t[n // 2],
            "p95": t[min(n - 1, int(n * 0.95))],
            "p99": t[min(n - 1, int(n * 0.99))],
            "max": t[-1],
            "mean": statistics.fmean(t),
            "ops_per_s": 1000.0 / statistics.fmean(t)
            if statistics.fmean(t) > 0
            else 0.0,
        }


def _random_string(n: int) -> str:
    # Short alphabet so random doesn't dominate cost — payload size is what matters.
    return (string.ascii_letters * ((n // len(string.ascii_letters)) + 1))[:n]


def _build_wide_dict(keys: int) -> dict[str, str]:
    # Mix of short and medium values to avoid trivially-compressible repetition.
    return {f"key_{i:04d}": f"value_{i}_{_random_string(20)}" for i in range(keys)}


def _build_deep_nested(levels: int) -> dict[str, Any]:
    d: Any = {"leaf": "bottom"}
    for i in range(levels):
        d = {f"level_{i}": d, "sibling": i}
    return d


def _build_ref_dict(count: int, entity: str, project: str) -> dict[str, str]:
    # Synthetic ref URIs; the server doesn't resolve them during the op call,
    # but the adapter still has to deep-copy them as part of inputs.
    return {
        f"ref_{i:03d}": f"weave:///{entity}/{project}/object/example:{uuid.uuid4().hex}"
        for i in range(count)
    }


@weave.op
def small_op(x: int) -> int:
    return x + 1


@weave.op
def dict_input_op(payload: dict[str, Any]) -> int:
    return len(payload)


@weave.op
def string_input_op(text: str) -> int:
    return len(text)


def _time(fn: Callable[[], Any]) -> float:
    t0 = time.perf_counter()
    fn()
    return (time.perf_counter() - t0) * 1000.0


def run_small_tight(client: WeaveClient, iterations: int) -> ScenarioResult:
    r = ScenarioResult("small_tight", "x+1 op, tight loop", iterations)
    small_op(0)  # warm-up
    for i in range(iterations):
        t0 = time.perf_counter()
        small_op(i)
        r.times_ms.append((time.perf_counter() - t0) * 1000.0)
    client.flush()
    return r


def run_wide_dict(client: WeaveClient, iterations: int) -> ScenarioResult:
    payload = _build_wide_dict(WIDE_DICT_KEYS)
    r = ScenarioResult(
        "wide_dict_input", f"{WIDE_DICT_KEYS}-key dict input", iterations
    )
    dict_input_op(payload)
    for _ in range(iterations):
        r.times_ms.append(_time(lambda: dict_input_op(payload)))
    client.flush()
    return r


def run_deep_nested(client: WeaveClient, iterations: int) -> ScenarioResult:
    payload = _build_deep_nested(DEEP_NEST_LEVELS)
    r = ScenarioResult(
        "deep_nested_input", f"{DEEP_NEST_LEVELS}-level nested dict", iterations
    )
    dict_input_op(payload)
    for _ in range(iterations):
        r.times_ms.append(_time(lambda: dict_input_op(payload)))
    client.flush()
    return r


def run_long_string(client: WeaveClient, iterations: int) -> ScenarioResult:
    payload = _random_string(LONG_STRING_BYTES)
    r = ScenarioResult(
        "long_string_input", f"{LONG_STRING_BYTES / 1e6:.1f}MB string", iterations
    )
    string_input_op(payload)
    for _ in range(iterations):
        r.times_ms.append(_time(lambda: string_input_op(payload)))
    client.flush()
    return r


def run_many_refs(
    client: WeaveClient, iterations: int, entity: str, project: str
) -> ScenarioResult:
    payload = _build_ref_dict(MANY_REFS_COUNT, entity, project)
    r = ScenarioResult(
        "many_refs_input", f"{MANY_REFS_COUNT} ref strings in inputs", iterations
    )
    dict_input_op(payload)
    for _ in range(iterations):
        r.times_ms.append(_time(lambda: dict_input_op(payload)))
    client.flush()
    return r


def run_dataset_publish(client: WeaveClient, iterations: int) -> list[ScenarioResult]:
    results = []
    for rows in DATASET_ROW_COUNTS:
        data = [{"i": i, "text": _random_string(64)} for i in range(rows)]
        r = ScenarioResult(
            f"dataset_publish_{rows}",
            f"weave.publish(Dataset(rows={rows}))",
            iterations,
        )
        weave.publish(weave.Dataset(rows=data), name=f"perf_ds_warmup_{rows}")
        for i in range(iterations):
            ds = weave.Dataset(rows=data)
            name = f"perf_ds_{rows}_{i}_{uuid.uuid4().hex[:8]}"
            t0 = time.perf_counter()
            weave.publish(ds, name=name)
            r.times_ms.append((time.perf_counter() - t0) * 1000.0)
        client.flush()
        results.append(r)
    return results


def run_table_create_direct(
    client: WeaveClient, iterations: int, project_id: str
) -> list[ScenarioResult]:
    results = []
    for rows in TABLE_ROW_COUNTS:
        payload = [{"i": i, "text": _random_string(64)} for i in range(rows)]
        r = ScenarioResult(
            f"table_create_direct_{rows}",
            f"server.table_create({rows} rows), bypasses tracing",
            iterations,
        )
        # Warm-up.
        client.server.table_create(
            tsi.TableCreateReq(
                table=tsi.TableSchemaForInsert(project_id=project_id, rows=payload)
            )
        )
        for _ in range(iterations):
            req = tsi.TableCreateReq(
                table=tsi.TableSchemaForInsert(project_id=project_id, rows=payload)
            )
            t0 = time.perf_counter()
            client.server.table_create(req)
            r.times_ms.append((time.perf_counter() - t0) * 1000.0)
        results.append(r)
    return results


def print_summary(results: list[ScenarioResult]) -> None:
    header = f"{'scenario':<30} {'payload':<45} {'n':>5} {'p50':>8} {'p95':>8} {'p99':>8} {'max':>8} {'mean':>8} {'ops/s':>8}"
    print("\n" + "=" * len(header))
    print(header)
    print("-" * len(header))
    for r in results:
        s = r.summary()
        if not s:
            continue
        print(
            f"{r.name:<30} {r.payload_desc:<45} "
            f"{int(s['n']):>5} "
            f"{s['p50']:>7.1f}ms "
            f"{s['p95']:>7.1f}ms "
            f"{s['p99']:>7.1f}ms "
            f"{s['max']:>7.1f}ms "
            f"{s['mean']:>7.1f}ms "
            f"{s['ops_per_s']:>7.1f}"
        )
    print("=" * len(header) + "\n")


SCENARIO_NAMES = (
    "small_tight",
    "wide_dict_input",
    "deep_nested_input",
    "long_string_input",
    "many_refs_input",
    "dataset_publish",
    "table_create_direct",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load test for ExternalTraceServer deep-copy overhead (PR #6670)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "-p",
        "--project",
        default="perf-deepcopy",
        help="Weave project (default: perf-deepcopy). Use entity/project or just project.",
    )
    parser.add_argument(
        "-i",
        "--iterations",
        type=int,
        default=200,
        help="Per-scenario iteration count (default: 200). "
        "Large-payload scenarios (long_string, 10k-row dataset) run the same count; "
        "dial down if network bound.",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=SCENARIO_NAMES,
        default=list(SCENARIO_NAMES),
        help="Which scenarios to run (default: all).",
    )
    parser.add_argument(
        "--entity",
        default=None,
        help="Entity for synthetic ref URIs. Defaults to the client's entity.",
    )
    args = parser.parse_args()

    print(f"\nInitializing weave: project={args.project} iterations={args.iterations}")
    client = weave.init(args.project)
    entity = args.entity or client.entity
    project = client.project
    project_id = f"{entity}/{project}"
    print(f"Connected. entity={entity} project={project}\n")

    results: list[ScenarioResult] = []

    if "small_tight" in args.scenarios:
        print(f"[small_tight] running {SMALL_TIGHT_ITERATIONS} ops...")
        results.append(run_small_tight(client, SMALL_TIGHT_ITERATIONS))

    if "wide_dict_input" in args.scenarios:
        print(
            f"[wide_dict_input] running {args.iterations} ops ({WIDE_DICT_KEYS} keys)..."
        )
        results.append(run_wide_dict(client, args.iterations))

    if "deep_nested_input" in args.scenarios:
        print(
            f"[deep_nested_input] running {args.iterations} ops ({DEEP_NEST_LEVELS} levels)..."
        )
        results.append(run_deep_nested(client, args.iterations))

    if "long_string_input" in args.scenarios:
        print(
            f"[long_string_input] running {args.iterations} ops ({LONG_STRING_BYTES / 1e6:.1f}MB each)..."
        )
        results.append(run_long_string(client, args.iterations))

    if "many_refs_input" in args.scenarios:
        print(
            f"[many_refs_input] running {args.iterations} ops ({MANY_REFS_COUNT} refs)..."
        )
        results.append(run_many_refs(client, args.iterations, entity, project))

    if "dataset_publish" in args.scenarios:
        print(
            f"[dataset_publish] running {args.iterations} publishes at sizes {DATASET_ROW_COUNTS}..."
        )
        results.extend(run_dataset_publish(client, args.iterations))

    if "table_create_direct" in args.scenarios:
        print(
            f"[table_create_direct] running {args.iterations} creates at sizes {TABLE_ROW_COUNTS}..."
        )
        results.extend(run_table_create_direct(client, args.iterations, project_id))

    print_summary(results)


if __name__ == "__main__":
    main()
