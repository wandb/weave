"""Benchmark: object creation and query performance.

Measures the time to create N versions of M different objects, plus query times.
Run against SQLite or ClickHouse to compare baselines.

Usage:
  # SQLite (fast, local baseline):
  nox --no-install -e "tests-3.12(shard='trace')" -- \
    tests/trace/bench_obj_create.py -v -s --trace-server=sqlite

  # ClickHouse:
  nox --no-install -e "tests-3.12(shard='trace')" -- \
    tests/trace/bench_obj_create.py -v -s --trace-server=clickhouse --clickhouse-process=true

After implementing the min(created_at) change, re-run and compare output.
"""

import time

from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.common_interface import SortBy

# Tunable parameters
NUM_OBJECTS = 100
NUM_VERSIONS_PER_OBJECT = 100


def _make_val(obj_idx: int, ver_idx: int) -> dict:
    """Generate a unique value for each object version."""
    return {
        "name": f"object_{obj_idx}",
        "version": ver_idx,
        "data": f"payload_{obj_idx}_{ver_idx}",
        "config": {"lr": 0.001 * ver_idx, "epochs": ver_idx + 1},
    }


def _objs_query(
    client: WeaveClient,
    object_id: str,
    latest_only: bool = False,
) -> list[tsi.ObjSchema]:
    return client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                object_ids=[object_id],
                latest_only=latest_only,
            ),
            sort_by=[SortBy(field="created_at", direction="asc")],
        )
    ).objs


def _objs_query_all(client: WeaveClient) -> list[tsi.ObjSchema]:
    """Query all objects (no filter), as a user listing their project would."""
    return client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=True),
        )
    ).objs


# ── Benchmark: bulk object creation ─────────────────────────────────


def test_bench_obj_create(client: WeaveClient):
    """Create NUM_VERSIONS_PER_OBJECT versions of NUM_OBJECTS objects.

    This is the hot path that the dedup-before-insert change would affect:
    each obj_create currently does a blind INSERT; the proposed change adds
    a SELECT check before inserting.
    """
    project_id = client._project_id()

    # Phase 1: Create all objects and versions
    t0 = time.perf_counter()
    digests: dict[str, list[str]] = {}  # object_id -> [digest, ...]

    for obj_idx in range(NUM_OBJECTS):
        object_id = f"bench_obj_{obj_idx}"
        digests[object_id] = []
        for ver_idx in range(NUM_VERSIONS_PER_OBJECT):
            val = _make_val(obj_idx, ver_idx)
            resp = client.server.obj_create(
                tsi.ObjCreateReq(
                    obj=tsi.ObjSchemaForInsert(
                        project_id=project_id,
                        object_id=object_id,
                        val=val,
                    )
                )
            )
            digests[object_id].append(resp.digest)

    t_create = time.perf_counter() - t0
    total_versions = NUM_OBJECTS * NUM_VERSIONS_PER_OBJECT

    print(f"\n{'=' * 60}")
    print(
        f"CREATE: {total_versions} versions ({NUM_OBJECTS} objects x {NUM_VERSIONS_PER_OBJECT} versions)"
    )
    print(f"  Total time:   {t_create:.2f}s")
    print(f"  Per version:  {t_create / total_versions * 1000:.2f}ms")
    print(f"  Throughput:   {total_versions / t_create:.0f} versions/s")

    # Phase 2: Query single object (all versions)
    t0 = time.perf_counter()
    sample_obj = "bench_obj_0"
    objs = _objs_query(client, sample_obj)
    t_query_single = time.perf_counter() - t0

    assert len(objs) == NUM_VERSIONS_PER_OBJECT, (
        f"Expected {NUM_VERSIONS_PER_OBJECT} versions for {sample_obj}, got {len(objs)}"
    )
    # Verify version indices are sequential
    for i, obj in enumerate(objs):
        assert obj.version_index == i, (
            f"Version index mismatch: expected {i}, got {obj.version_index} "
            f"(digest={obj.digest})"
        )

    print(f"\nQUERY single object ({NUM_VERSIONS_PER_OBJECT} versions):")
    print(f"  Time: {t_query_single * 1000:.1f}ms")

    # Phase 3: Query all latest versions
    t0 = time.perf_counter()
    latest_objs = _objs_query_all(client)
    t_query_latest = time.perf_counter() - t0

    assert len(latest_objs) >= NUM_OBJECTS, (
        f"Expected at least {NUM_OBJECTS} latest objects, got {len(latest_objs)}"
    )

    print(f"\nQUERY all latest ({len(latest_objs)} objects):")
    print(f"  Time: {t_query_latest * 1000:.1f}ms")

    # Phase 4: Re-publish existing content (dedup path)
    # This is the exact path that gets a dedup check added
    t0 = time.perf_counter()
    num_republish = NUM_OBJECTS  # re-publish v0 of each object
    for obj_idx in range(NUM_OBJECTS):
        object_id = f"bench_obj_{obj_idx}"
        val = _make_val(obj_idx, 0)  # same content as v0
        client.server.obj_create(
            tsi.ObjCreateReq(
                obj=tsi.ObjSchemaForInsert(
                    project_id=project_id,
                    object_id=object_id,
                    val=val,
                )
            )
        )
    t_republish = time.perf_counter() - t0

    print(f"\nREPUBLISH: {num_republish} objects (same content as v0):")
    print(f"  Total time:  {t_republish:.2f}s")
    print(f"  Per republish: {t_republish / num_republish * 1000:.2f}ms")

    # Phase 5: Query after republish to verify version count
    t0 = time.perf_counter()
    objs_after = _objs_query(client, "bench_obj_0")
    t_query_after = time.perf_counter() - t0

    print(f"\nQUERY after republish ({len(objs_after)} versions):")
    print(f"  Time: {t_query_after * 1000:.1f}ms")

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"  obj_create rate:    {total_versions / t_create:.0f}/s")
    print(f"  republish rate:     {num_republish / t_republish:.0f}/s")
    print(f"  query single:       {t_query_single * 1000:.1f}ms")
    print(f"  query all latest:   {t_query_latest * 1000:.1f}ms")
    print(f"  query after repub:  {t_query_after * 1000:.1f}ms")
    print(f"{'=' * 60}\n")


# ── Benchmark: query-heavy workload ─────────────────────────────────


def test_bench_query_versions(client: WeaveClient):
    """Measure query performance with varying numbers of versions.

    Creates objects with 1, 10, 50, 100 versions and times queries for each.
    This isolates the cost of the version_index window function.
    """
    project_id = client._project_id()
    version_counts = [1, 10, 50, 100, 250, 500, 1000]

    print(f"\n{'=' * 60}")
    print("QUERY SCALING BY VERSION COUNT")

    for n_versions in version_counts:
        object_id = f"bench_scale_{n_versions}"

        # Create versions
        for v in range(n_versions):
            client.server.obj_create(
                tsi.ObjCreateReq(
                    obj=tsi.ObjSchemaForInsert(
                        project_id=project_id,
                        object_id=object_id,
                        val=_make_val(0, v),
                    )
                )
            )

        # Time the query (run 5x, take median)
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            objs = _objs_query(client, object_id)
            times.append(time.perf_counter() - t0)

        assert len(objs) == n_versions
        median_ms = sorted(times)[len(times) // 2] * 1000
        print(f"  {n_versions:>3} versions: {median_ms:.1f}ms (median of 5)")

    # Also measure query across all objects in the project
    t0 = time.perf_counter()
    all_latest = _objs_query_all(client)
    t_all = time.perf_counter() - t0
    print(f"\n  All latest ({len(all_latest)} objects): {t_all * 1000:.1f}ms")
    print(f"{'=' * 60}\n")


# ── Benchmark: concurrent-style object creation ─────────────────────


def test_bench_obj_create_many_objects_few_versions(client: WeaveClient):
    """Inverse pattern: many distinct objects with few versions each.

    This stresses the partition-creation side of the window function
    rather than the per-partition sorting.
    """
    project_id = client._project_id()
    n_objects = 500
    n_versions = 5

    t0 = time.perf_counter()
    for obj_idx in range(n_objects):
        for ver_idx in range(n_versions):
            client.server.obj_create(
                tsi.ObjCreateReq(
                    obj=tsi.ObjSchemaForInsert(
                        project_id=project_id,
                        object_id=f"bench_wide_{obj_idx}",
                        val=_make_val(obj_idx, ver_idx),
                    )
                )
            )
    t_create = time.perf_counter() - t0
    total = n_objects * n_versions

    print(f"\n{'=' * 60}")
    print(
        f"WIDE CREATE: {total} versions ({n_objects} objects x {n_versions} versions)"
    )
    print(f"  Total time:  {t_create:.2f}s")
    print(f"  Per version: {t_create / total * 1000:.2f}ms")
    print(f"  Throughput:  {total / t_create:.0f} versions/s")

    # Query all latest
    t0 = time.perf_counter()
    latest = _objs_query_all(client)
    t_query = time.perf_counter() - t0
    print(f"\n  Query all latest ({len(latest)} objects): {t_query * 1000:.1f}ms")
    print(f"{'=' * 60}\n")
