import threading
import time

from weave.trace_server.op_ref_cache import OpRefCache


def test_get_miss_returns_empty():
    cache = OpRefCache()
    assert cache.get_many("proj", {"op_a", "op_b"}) == {}


def test_put_and_get():
    cache = OpRefCache()
    cache.put_many("proj", {"op_a": "uri_a", "op_b": "uri_b"})
    result = cache.get_many("proj", {"op_a", "op_b", "op_c"})
    assert result == {"op_a": "uri_a", "op_b": "uri_b"}


def test_project_isolation():
    cache = OpRefCache()
    cache.put_many("proj1", {"op_a": "uri_1"})
    cache.put_many("proj2", {"op_a": "uri_2"})

    assert cache.get_many("proj1", {"op_a"}) == {"op_a": "uri_1"}
    assert cache.get_many("proj2", {"op_a"}) == {"op_a": "uri_2"}


def test_ttl_expiry():
    cache = OpRefCache(ttl_seconds=0.05)
    cache.put_many("proj", {"op_a": "uri_a"})

    assert cache.get_many("proj", {"op_a"}) == {"op_a": "uri_a"}
    time.sleep(0.06)
    assert cache.get_many("proj", {"op_a"}) == {}


def test_eviction_at_capacity():
    cache = OpRefCache(max_size=10)
    # Fill to capacity
    cache.put_many("proj", {f"op_{i}": f"uri_{i}" for i in range(10)})
    # Adding one more should trigger eviction of oldest 10%
    time.sleep(0.001)  # Ensure new entries have a later expiry
    cache.put_many("proj", {"op_new": "uri_new"})

    # Should have evicted 1 entry (10% of 11, rounded up to 1)
    all_hits = cache.get_many("proj", {f"op_{i}" for i in range(10)} | {"op_new"})
    assert len(all_hits) == 10
    assert all_hits["op_new"] == "uri_new"


def test_overwrite_refreshes_entry():
    cache = OpRefCache(ttl_seconds=0.1)
    cache.put_many("proj", {"op_a": "uri_old"})
    time.sleep(0.06)
    cache.put_many("proj", {"op_a": "uri_new"})
    time.sleep(0.06)
    # Original TTL would have expired, but overwrite refreshed it
    assert cache.get_many("proj", {"op_a"}) == {"op_a": "uri_new"}


def test_thread_safety():
    cache = OpRefCache()
    errors: list[Exception] = []

    def writer(thread_id: int) -> None:
        try:
            for i in range(100):
                cache.put_many(f"proj_{thread_id}", {f"op_{i}": f"uri_{thread_id}_{i}"})
        except Exception as e:
            errors.append(e)

    def reader(thread_id: int) -> None:
        try:
            for i in range(100):
                cache.get_many(f"proj_{thread_id}", {f"op_{i}" for i in range(100)})
        except Exception as e:
            errors.append(e)

    threads = []
    for t_id in range(4):
        threads.append(threading.Thread(target=writer, args=(t_id,)))
        threads.append(threading.Thread(target=reader, args=(t_id,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []


def test_cross_project_isolation():
    """Adversarial: cached data must never leak between projects."""
    # Identical op names across 50 projects get independent URIs
    cache = OpRefCache()
    projects = [f"proj_{i}" for i in range(50)]
    for proj in projects:
        cache.put_many(proj, {"train": f"uri://{proj}/train"})
    for proj in projects:
        assert cache.get_many(proj, {"train"}) == {"train": f"uri://{proj}/train"}

    # Overwriting in "attacker" project doesn't touch "victim"
    cache.put_many("victim", {"op": "uri://victim/op:v1"})
    cache.put_many("attacker", {"op": "uri://attacker/MALICIOUS"})
    assert cache.get_many("victim", {"op"}) == {"op": "uri://victim/op:v1"}

    # Eviction pressure: surviving entries still map to correct project
    cache2 = OpRefCache(max_size=20)
    cache2.put_many("proj_a", {f"op_{i}": f"uri://a/{i}" for i in range(15)})
    time.sleep(0.001)
    cache2.put_many("proj_b", {f"op_{i}": f"uri://b/{i}" for i in range(10)})
    for uri in cache2.get_many("proj_b", {f"op_{i}" for i in range(10)}).values():
        assert "uri://b/" in uri
    for uri in cache2.get_many("proj_a", {f"op_{i}" for i in range(15)}).values():
        assert "uri://a/" in uri

    # Expired entry in project_a doesn't resurface in project_b
    cache3 = OpRefCache(ttl_seconds=0.05)
    cache3.put_many("proj_a", {"shared": "uri://a/shared"})
    time.sleep(0.06)
    assert cache3.get_many("proj_b", {"shared"}) == {}
    assert cache3.get_many("proj_a", {"shared"}) == {}


def test_concurrent_cross_project_isolation():
    """20 threads writing/reading different projects must never see each other's data."""
    cache = OpRefCache()
    op_names = {f"op_{i}" for i in range(50)}
    errors: list[str] = []

    def writer_then_reader(proj: str) -> None:
        cache.put_many(proj, {op: f"uri://{proj}/{op}" for op in op_names})
        for op_name, uri in cache.get_many(proj, op_names).items():
            if uri != f"uri://{proj}/{op_name}":
                errors.append(f"{proj} got {uri}, expected uri://{proj}/{op_name}")

    threads = [
        threading.Thread(target=writer_then_reader, args=(f"proj_{i}",))
        for i in range(20)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Cross-project leaks: {errors}"
