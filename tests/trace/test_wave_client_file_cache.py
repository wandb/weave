import threading
from concurrent.futures import Future
from unittest.mock import patch

import httpx
import pytest

from weave.trace.weave_client import WeaveClient
from weave.trace.weave_client_send_file_cache import (
    ThreadSafeLRUCache,
    WeaveClientSendFileCache,
)
from weave.trace_server.trace_server_interface import FileCreateReq, FileCreateRes
from weave.trace_server_bindings.remote_http_trace_server import RemoteHTTPTraceServer


@pytest.mark.parametrize(
    ("init_size", "expected"),
    [(None, 1000), (100, 100), (0, 0), (-10, 0)],
)
def test_lru_cache_init_max_size(init_size, expected):
    """Default, custom, zero (unlimited), and negative (clamped to 0) max_size."""
    cache = (
        ThreadSafeLRUCache()
        if init_size is None
        else ThreadSafeLRUCache(max_size=init_size)
    )
    assert cache.max_size == expected


def test_lru_cache_put_get_update_delete_contains():
    """Basic put/get, overwrite, missing-key, delete, delete-missing, contains."""
    cache = ThreadSafeLRUCache()
    assert cache.get("nonexistent") is None
    assert cache.contains("nonexistent") is False

    cache.put("key1", "value1")
    assert cache.get("key1") == "value1"
    assert cache.contains("key1") is True

    cache.put("key1", "value2")
    assert cache.get("key1") == "value2"

    cache.delete("key1")
    assert cache.get("key1") is None
    cache.delete("nonexistent")  # no-op, must not raise


def test_lru_cache_size_and_clear():
    """size() tracks puts/deletes/clear; clear() empties the cache."""
    cache = ThreadSafeLRUCache()
    assert cache.size() == 0
    cache.put("key1", "value1")
    assert cache.size() == 1
    cache.put("key2", "value2")
    assert cache.size() == 2
    cache.delete("key1")
    assert cache.size() == 1
    cache.clear()
    assert cache.size() == 0
    assert cache.get("key2") is None


def test_lru_cache_max_size_property():
    """max_size getter/setter; setting negative clamps to 0 (unlimited)."""
    cache = ThreadSafeLRUCache(max_size=100)
    assert cache.max_size == 100
    cache.max_size = 200
    assert cache.max_size == 200
    cache.max_size = 0
    assert cache.max_size == 0
    cache.max_size = -10
    assert cache.max_size == 0


def test_lru_cache_eviction_and_update_order():
    """Insertion evicts oldest; get() and put()-update both refresh recency."""
    cache = ThreadSafeLRUCache(max_size=3)
    cache.put("key1", "value1")
    cache.put("key2", "value2")
    cache.put("key3", "value3")

    # Insert key4 -> evicts LRU (key1).
    cache.put("key4", "value4")
    assert cache.get("key1") is None
    assert cache.get("key2") == "value2"
    assert cache.get("key3") == "value3"
    assert cache.get("key4") == "value4"

    # get(key2) makes key3 the LRU; key5 evicts key3.
    cache.get("key2")
    cache.put("key5", "value5")
    assert cache.get("key2") == "value2"
    assert cache.get("key3") is None
    assert cache.get("key4") == "value4"
    assert cache.get("key5") == "value5"

    # put-update refreshes recency: re-fill, update key_a, insert evicts key_b.
    cache.clear()
    cache.put("key_a", "a")
    cache.put("key_b", "b")
    cache.put("key_c", "c")
    cache.put("key_a", "a_updated")
    cache.put("key_d", "d")
    assert cache.get("key_a") == "a_updated"
    assert cache.get("key_b") is None
    assert cache.get("key_c") == "c"
    assert cache.get("key_d") == "d"


def test_lru_cache_max_size_reduction_evicts_lru():
    """Shrinking max_size evicts the least recently used entries."""
    cache = ThreadSafeLRUCache(max_size=5)
    for i in range(5):
        cache.put(f"key{i}", f"value{i}")
    assert cache.size() == 5

    for i in range(5):
        cache.get(f"key{i}")

    cache.max_size = 3
    assert cache.size() == 3
    assert cache.get("key0") is None
    assert cache.get("key1") is None
    assert cache.get("key2") == "value2"
    assert cache.get("key3") == "value3"
    assert cache.get("key4") == "value4"


def test_lru_cache_unlimited_size_keeps_all():
    """max_size=0 disables eviction; many entries all persist."""
    cache = ThreadSafeLRUCache(max_size=0)
    for i in range(1000):
        cache.put(f"key{i}", f"value{i}")
    assert cache.size() == 1000
    for i in range(1000):
        assert cache.get(f"key{i}") == f"value{i}"


def test_lru_cache_thread_safety():
    """Concurrent put/get from many threads preserves every entry."""
    cache = ThreadSafeLRUCache(max_size=1000)
    num_threads = 10
    operations_per_thread = 100

    def worker(thread_id):
        for i in range(operations_per_thread):
            key = f"key{thread_id}_{i}"
            value = f"value{thread_id}_{i}"
            cache.put(key, value)
            assert cache.get(key) == value

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    for i in range(num_threads):
        for j in range(operations_per_thread):
            assert cache.get(f"key{i}_{j}") == f"value{i}_{j}"
    assert cache.size() == num_threads * operations_per_thread


@pytest.mark.parametrize("init_size", [None, 100])
def test_send_file_cache_init_and_max_size_property(init_size):
    """Default/custom init plus max_size getter/setter including unlimited."""
    expected = 1000 if init_size is None else init_size
    cache = (
        WeaveClientSendFileCache()
        if init_size is None
        else (WeaveClientSendFileCache(max_size=init_size))
    )
    assert cache.max_size == expected
    cache.max_size = 200
    assert cache.max_size == 200
    cache.max_size = 0
    assert cache.max_size == 0


def test_send_file_cache_key_generation():
    """`_key` is unique per (project_id, name, content) and stable for equal reqs."""
    cache = WeaveClientSendFileCache()
    req1 = FileCreateReq(project_id="test", name="file1", content=b"content1")
    req2 = FileCreateReq(project_id="test", name="file2", content=b"content1")
    req3 = FileCreateReq(project_id="other", name="file1", content=b"content1")
    req4 = FileCreateReq(project_id="test", name="file1", content=b"different")

    key1 = cache._key(req1)
    assert key1 != cache._key(req2)
    assert key1 != cache._key(req3)
    assert key1 != cache._key(req4)
    assert key1 == cache._key(
        FileCreateReq(project_id="test", name="file1", content=b"content1")
    )


def test_send_file_cache_put_get_update_delete_size():
    """put/get, overwrite, missing-key, delete, delete-missing, size, clear."""
    cache = WeaveClientSendFileCache()
    assert cache.size() == 0

    miss = FileCreateReq(project_id="test", name="nonexistent", content=b"test")
    assert cache.get(miss) is None

    req = FileCreateReq(project_id="test", name="test", content=b"test")
    cache.put(req, FileCreateRes(digest="digest1"))
    assert cache.get(req) == FileCreateRes(digest="digest1")
    assert cache.size() == 1

    cache.put(req, FileCreateRes(digest="digest2"))
    assert cache.get(req) == FileCreateRes(digest="digest2")
    assert cache.size() == 1

    cache.delete(req)
    assert cache.get(req) is None
    cache.delete(req)  # delete-missing no-op

    req1 = FileCreateReq(project_id="test", name="file1", content=b"content1")
    req2 = FileCreateReq(project_id="test", name="file2", content=b"content2")
    cache.put(req1, FileCreateRes(digest="d1"))
    cache.put(req2, FileCreateRes(digest="d2"))
    assert cache.size() == 2
    cache.clear()
    assert cache.size() == 0
    assert cache.get(req1) is None
    assert cache.get(req2) is None


def test_send_file_cache_lru_eviction():
    """LRU eviction over FileCreateReq keys, with get() refreshing recency."""
    cache = WeaveClientSendFileCache(max_size=2)
    req1 = FileCreateReq(project_id="test", name="file1", content=b"content1")
    req2 = FileCreateReq(project_id="test", name="file2", content=b"content2")
    req3 = FileCreateReq(project_id="test", name="file3", content=b"content3")
    res1 = FileCreateRes(digest="digest1")
    res2 = FileCreateRes(digest="digest2")
    res3 = FileCreateRes(digest="digest3")

    cache.put(req1, res1)
    cache.put(req2, res2)
    assert cache.size() == 2

    cache.put(req3, res3)
    assert cache.size() == 2
    assert cache.get(req1) is None
    assert cache.get(req2) == res2
    assert cache.get(req3) == res3

    cache.get(req2)  # req3 becomes LRU
    cache.put(req1, res1)
    assert cache.size() == 2
    assert cache.get(req1) == res1
    assert cache.get(req2) == res2
    assert cache.get(req3) is None


@pytest.fixture
def offline_client(monkeypatch):
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("WEAVE_RETRY_MAX_INTERVAL", "0.01")
    monkeypatch.setenv("WEAVE_ENABLE_WAL", "false")
    server = RemoteHTTPTraceServer("http://example.com")
    client = WeaveClient(
        entity="ent",
        project="proj",
        server=server,
        ensure_project_exists=False,
    )
    return client, server


@pytest.mark.disable_logging_error_check
def test_failed_file_create_evicts_cache_and_retries_on_next_call(offline_client):
    """A failed file_create future must be evicted so the next call retries."""
    client, server = offline_client
    req = FileCreateReq(project_id="ent/proj", name="f", content=b"hello")

    with patch.object(server, "file_create", side_effect=_make_502()):
        fut1 = client._send_file_create(req)
        client.future_executor.flush()
        if client.future_executor_fastlane is not None:
            client.future_executor_fastlane.flush()

    assert fut1.exception() is not None
    assert client.send_file_cache.get(req) is None

    success_res = FileCreateRes(digest="abc")
    with patch.object(server, "file_create", return_value=success_res):
        fut2 = client._send_file_create(req)
        client.future_executor.flush()
        if client.future_executor_fastlane is not None:
            client.future_executor_fastlane.flush()

    assert fut2 is not fut1
    assert fut2.result() == success_res
    assert client.send_file_cache.get(req) is fut2


def test_successful_file_create_stays_cached(offline_client):
    """A successful file_create must stay cached so duplicates are deduped."""
    client, server = offline_client
    req = FileCreateReq(project_id="ent/proj", name="f", content=b"hello")
    success_res = FileCreateRes(digest="abc")

    with patch.object(server, "file_create", return_value=success_res):
        fut1 = client._send_file_create(req)
        client.future_executor.flush()
        if client.future_executor_fastlane is not None:
            client.future_executor_fastlane.flush()

    assert client.send_file_cache.get(req) is fut1
    fut2 = client._send_file_create(req)
    assert fut2 is fut1


@pytest.mark.disable_logging_error_check
def test_stale_failure_callback_does_not_evict_replacement_entry(offline_client):
    """Late failure of an LRU-evicted in-flight future must not wipe a replacement entry.

    Scenario: req_a's in-flight future is LRU-evicted while still pending. The same key
    is later re-populated by a successful upload. When the original future finally fails,
    its done-callback must not delete the unrelated, freshly-cached success.
    """
    client, server = offline_client
    client.send_file_cache.max_size = 1  # force LRU eviction after each put

    req_a = FileCreateReq(project_id="ent/proj", name="a", content=b"a")
    req_b = FileCreateReq(project_id="ent/proj", name="b", content=b"b")

    controllable_future: Future[FileCreateRes] = Future()
    target_executor = client.future_executor_fastlane or client.future_executor
    original_defer = target_executor.defer
    call_count = [0]

    def fake_defer(fn, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return controllable_future
        return original_defer(fn, *args, **kwargs)

    with patch.object(target_executor, "defer", side_effect=fake_defer):
        # 1. Put req_a -> controllable_future (in-flight). Callback wired.
        fut_a_initial = client._send_file_create(req_a)
        assert fut_a_initial is controllable_future
        assert client.send_file_cache.get(req_a) is controllable_future

        # 2. Put req_b -> LRU evicts req_a from the cache.
        with patch.object(
            server, "file_create", return_value=FileCreateRes(digest="b")
        ):
            client._send_file_create(req_b)
            client.future_executor.flush()
            if client.future_executor_fastlane is not None:
                client.future_executor_fastlane.flush()
        assert client.send_file_cache.get(req_a) is None

        # 3. Cache miss for req_a -> fresh successful upload takes the slot.
        with patch.object(
            server, "file_create", return_value=FileCreateRes(digest="a")
        ):
            fut_a_v2 = client._send_file_create(req_a)
            client.future_executor.flush()
            if client.future_executor_fastlane is not None:
                client.future_executor_fastlane.flush()
        assert client.send_file_cache.get(req_a) is fut_a_v2

    # 4. Original future fails late. Its callback runs delete(req_a) and wrongly
    #    evicts the replacement entry.
    controllable_future.set_exception(
        httpx.HTTPStatusError(
            "502",
            request=httpx.Request("POST", "http://example.com/file/create"),
            response=httpx.Response(
                status_code=502,
                request=httpx.Request("POST", "http://example.com/file/create"),
            ),
        )
    )

    assert client.send_file_cache.get(req_a) is fut_a_v2


def _make_502() -> httpx.HTTPStatusError:
    response = httpx.Response(
        status_code=502,
        request=httpx.Request("POST", "http://example.com/file/create"),
        content=b"Bad Gateway",
    )
    return httpx.HTTPStatusError("502", request=response.request, response=response)
