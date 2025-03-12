import threading

from weave.trace.weave_client_send_file_cache import (
    ThreadSafeLRUCache,
    WeaveClientSendFileCache,
)
from weave.trace_server.trace_server_interface import FileCreateReq, FileCreateRes


class TestThreadSafeLRUCache:
    """Test the ThreadSafeLRUCache class."""

    def test_init_default(self):
        """Test that the cache initializes with default max_size."""
        cache = ThreadSafeLRUCache()
        assert cache.max_size == 1000

    def test_init_custom_size(self):
        """Test that the cache initializes with custom max_size."""
        cache = ThreadSafeLRUCache(max_size=100)
        assert cache.max_size == 100

    def test_init_zero_size(self):
        """Test that the cache initializes with zero max_size (unlimited)."""
        cache = ThreadSafeLRUCache(max_size=0)
        assert cache.max_size == 0

    def test_init_negative_size(self):
        """Test that negative max_size is handled correctly (converted to 0)."""
        cache = ThreadSafeLRUCache(max_size=-10)
        assert cache.max_size == 0

    def test_put_get_basic(self):
        """Test basic put and get operations."""
        cache = ThreadSafeLRUCache()
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent(self):
        """Test get on a non-existent key."""
        cache = ThreadSafeLRUCache()
        assert cache.get("nonexistent") is None

    def test_put_update(self):
        """Test updating an existing key."""
        cache = ThreadSafeLRUCache()
        cache.put("key1", "value1")
        cache.put("key1", "value2")
        assert cache.get("key1") == "value2"

    def test_delete(self):
        """Test deleting a key."""
        cache = ThreadSafeLRUCache()
        cache.put("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_delete_nonexistent(self):
        """Test deleting a non-existent key (should not raise an error)."""
        cache = ThreadSafeLRUCache()
        cache.delete("nonexistent")  # Should not raise an error

    def test_contains(self):
        """Test the contains method."""
        cache = ThreadSafeLRUCache()
        cache.put("key1", "value1")
        assert cache.contains("key1") is True
        assert cache.contains("nonexistent") is False

    def test_clear(self):
        """Test clearing the cache."""
        cache = ThreadSafeLRUCache()
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.clear()
        assert cache.size() == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_size(self):
        """Test the size method."""
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

    def test_max_size_property(self):
        """Test getting and setting the max_size property."""
        cache = ThreadSafeLRUCache(max_size=100)
        assert cache.max_size == 100
        cache.max_size = 200
        assert cache.max_size == 200
        cache.max_size = 0  # unlimited
        assert cache.max_size == 0
        cache.max_size = -10  # should convert to 0
        assert cache.max_size == 0

    def test_lru_eviction(self):
        """Test that LRU eviction works correctly."""
        cache = ThreadSafeLRUCache(max_size=3)
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")
        # Cache is now at max size (3)

        # Add a new key, should evict the least recently used (key1)
        cache.put("key4", "value4")
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

        # Access key2, making key3 the least recently used
        cache.get("key2")

        # Add a new key, should evict the least recently used (key3)
        cache.put("key5", "value5")
        assert cache.get("key2") == "value2"
        assert cache.get("key3") is None
        assert cache.get("key4") == "value4"
        assert cache.get("key5") == "value5"

    def test_lru_update(self):
        """Test that updating an existing key preserves LRU order."""
        cache = ThreadSafeLRUCache(max_size=3)
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        # Update key1, making it the most recently used
        cache.put("key1", "value1_updated")

        # Add a new key, should evict the least recently used (key2)
        cache.put("key4", "value4")
        assert cache.get("key1") == "value1_updated"
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_thread_safety(self):
        """Test that the cache is thread-safe."""
        cache = ThreadSafeLRUCache(max_size=1000)
        num_threads = 10
        operations_per_thread = 100

        def worker(thread_id):
            for i in range(operations_per_thread):
                key = f"key{thread_id}_{i}"
                value = f"value{thread_id}_{i}"
                cache.put(key, value)
                assert cache.get(key) == value

        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all keys are still there
        for i in range(num_threads):
            for j in range(operations_per_thread):
                key = f"key{i}_{j}"
                value = f"value{i}_{j}"
                assert cache.get(key) == value

        assert cache.size() == num_threads * operations_per_thread

    def test_max_size_reduction(self):
        """Test reducing max_size evicts the least recently used items."""
        cache = ThreadSafeLRUCache(max_size=5)
        for i in range(5):
            cache.put(f"key{i}", f"value{i}")

        assert cache.size() == 5

        # Access keys in a specific order to establish LRU order
        # Order of access (oldest to newest): key0, key1, key2, key3, key4
        for i in range(5):
            cache.get(f"key{i}")

        # Reduce max_size to 3, should keep the 3 most recently used: key2, key3, key4
        cache.max_size = 3

        assert cache.size() == 3
        # The 2 least recently used keys should be evicted (key0, key1)
        assert cache.get("key0") is None
        assert cache.get("key1") is None
        # The 3 most recently used keys should remain
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_unlimited_size(self):
        """Test that setting max_size to 0 allows unlimited entries."""
        cache = ThreadSafeLRUCache(max_size=0)  # unlimited

        # Add many entries, should not evict any
        for i in range(1000):
            cache.put(f"key{i}", f"value{i}")

        assert cache.size() == 1000

        # Check all entries are still there
        for i in range(1000):
            assert cache.get(f"key{i}") == f"value{i}"


class TestWeaveClientSendFileCache:
    """Test the WeaveClientSendFileCache class."""

    def test_init_default(self):
        """Test that the cache initializes with default max_size."""
        cache = WeaveClientSendFileCache()
        assert cache.max_size == 1000

    def test_init_custom_size(self):
        """Test that the cache initializes with custom max_size."""
        cache = WeaveClientSendFileCache(max_size=100)
        assert cache.max_size == 100

    def test_key_generation(self):
        """Test that the _key method generates unique keys for different requests."""
        cache = WeaveClientSendFileCache()

        req1 = FileCreateReq(project_id="test", name="file1", content=b"content1")
        req2 = FileCreateReq(project_id="test", name="file2", content=b"content1")
        req3 = FileCreateReq(project_id="other", name="file1", content=b"content1")
        req4 = FileCreateReq(project_id="test", name="file1", content=b"different")

        key1 = cache._key(req1)
        key2 = cache._key(req2)
        key3 = cache._key(req3)
        key4 = cache._key(req4)

        # Different requests should have different keys
        assert key1 != key2
        assert key1 != key3
        assert key1 != key4

        # Same request should have the same key
        assert key1 == cache._key(
            FileCreateReq(project_id="test", name="file1", content=b"content1")
        )

    def test_put_get_basic(self):
        """Test basic put and get operations."""
        cache = WeaveClientSendFileCache()
        req = FileCreateReq(project_id="test", name="test", content=b"test")
        res = FileCreateRes(digest="test_digest")

        cache.put(req, res)
        assert cache.get(req) == res

    def test_get_nonexistent(self):
        """Test get on a non-existent key."""
        cache = WeaveClientSendFileCache()
        req = FileCreateReq(project_id="test", name="nonexistent", content=b"test")
        assert cache.get(req) is None

    def test_put_update(self):
        """Test updating an existing key."""
        cache = WeaveClientSendFileCache()
        req = FileCreateReq(project_id="test", name="test", content=b"test")
        res1 = FileCreateRes(digest="digest1")
        res2 = FileCreateRes(digest="digest2")

        cache.put(req, res1)
        cache.put(req, res2)
        assert cache.get(req) == res2

    def test_clear(self):
        """Test clearing the cache."""
        cache = WeaveClientSendFileCache()
        req1 = FileCreateReq(project_id="test", name="file1", content=b"content1")
        req2 = FileCreateReq(project_id="test", name="file2", content=b"content2")
        res1 = FileCreateRes(digest="digest1")
        res2 = FileCreateRes(digest="digest2")

        cache.put(req1, res1)
        cache.put(req2, res2)
        assert cache.size() == 2

        cache.clear()
        assert cache.size() == 0
        assert cache.get(req1) is None
        assert cache.get(req2) is None

    def test_size(self):
        """Test the size method."""
        cache = WeaveClientSendFileCache()
        assert cache.size() == 0

        req1 = FileCreateReq(project_id="test", name="file1", content=b"content1")
        req2 = FileCreateReq(project_id="test", name="file2", content=b"content2")
        res1 = FileCreateRes(digest="digest1")
        res2 = FileCreateRes(digest="digest2")

        cache.put(req1, res1)
        assert cache.size() == 1
        cache.put(req2, res2)
        assert cache.size() == 2
        cache.clear()
        assert cache.size() == 0

    def test_max_size_property(self):
        """Test getting and setting the max_size property."""
        cache = WeaveClientSendFileCache(max_size=100)
        assert cache.max_size == 100

        cache.max_size = 200
        assert cache.max_size == 200

        cache.max_size = 0  # unlimited
        assert cache.max_size == 0

    def test_lru_eviction(self):
        """Test that LRU eviction works correctly."""
        cache = WeaveClientSendFileCache(max_size=2)

        req1 = FileCreateReq(project_id="test", name="file1", content=b"content1")
        req2 = FileCreateReq(project_id="test", name="file2", content=b"content2")
        req3 = FileCreateReq(project_id="test", name="file3", content=b"content3")

        res1 = FileCreateRes(digest="digest1")
        res2 = FileCreateRes(digest="digest2")
        res3 = FileCreateRes(digest="digest3")

        # Add two items, filling the cache
        cache.put(req1, res1)
        cache.put(req2, res2)
        assert cache.size() == 2

        # Add a third item, should evict the least recently used (req1)
        cache.put(req3, res3)
        assert cache.size() == 2
        assert cache.get(req1) is None
        assert cache.get(req2) == res2
        assert cache.get(req3) == res3

        # Access req2, making req3 the least recently used
        cache.get(req2)

        # Add req1 back, should evict req3
        cache.put(req1, res1)
        assert cache.size() == 2
        assert cache.get(req1) == res1
        assert cache.get(req2) == res2
        assert cache.get(req3) is None


def test_wave_client_file_cache_backwards_compatible():
    """Test that the cache is backwards compatible with the original test."""
    cache = WeaveClientSendFileCache()
    req = FileCreateReq(project_id="test", name="test", content=b"test")
    res = FileCreateRes(digest="test")
    cache.put(req, res)
    assert cache.get(req) == res
