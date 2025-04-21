import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from weave.trace.weave_client_send_file_cache import (
    ThreadSafeLRUCache,
    WeaveClientSendFileCache,
)
from weave.trace_server.trace_server_interface import FileCreateReq, FileCreateRes


# Add a Counter class since threading.Counter doesn't exist in standard library
class Counter:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()

    def increment(self, amount=1):
        with self._lock:
            self._value += amount

    def value(self):
        with self._lock:
            return self._value


def test_cache_memory_usage():
    """Test that the cache size is limited properly by LRU eviction."""
    # Create a cache with a small max size (100 entries)
    cache = ThreadSafeLRUCache(max_size=100)

    # Insert 1000 entries (10x max size)
    for i in range(1000):
        cache.put(f"key{i}", f"value{i}")

    # Verify that only max_size entries remain
    assert cache.size() == 100

    # Verify that only the most recently inserted entries remain
    for i in range(900):
        assert cache.get(f"key{i}") is None

    for i in range(900, 1000):
        assert cache.get(f"key{i}") == f"value{i}"


def test_cache_memory_usage_with_file_contents():
    """Test that the cache properly handles large file contents."""
    # Create a cache with a small max size
    cache = WeaveClientSendFileCache(max_size=10)

    # Create requests with realistic file sizes
    file_sizes = [1024, 2048, 4096, 8192, 16384]  # varying sizes in bytes

    # Insert 50 entries (5x max size) with random file contents
    for i in range(50):
        size = random.choice(file_sizes)
        content = bytes([random.randint(0, 255) for _ in range(size)])
        req = FileCreateReq(
            project_id=f"test_project_{i % 5}", name=f"file_{i}.txt", content=content
        )
        res = FileCreateRes(digest=f"digest_{i}")
        cache.put(req, res)

    # Verify that only max_size entries remain
    assert cache.size() == 10


def test_concurrent_access_with_high_load():
    """Test that the cache handles concurrent access correctly under high load."""
    cache = ThreadSafeLRUCache(max_size=500)
    num_threads = 20
    operations_per_thread = 1000

    # Set up tracking for successful operations
    success_counter = Counter()

    def worker(thread_id):
        for i in range(operations_per_thread):
            op = random.randint(0, 10)  # 0-8: read, 9-10: write
            key = f"key_{random.randint(0, 1000)}"

            if op < 8:  # 80% reads
                # Just read, don't care about result
                cache.get(key)
            else:  # 20% writes
                cache.put(key, f"value_{thread_id}_{i}")

            # Count successful operations
            success_counter.increment()

    # Start threads
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for future in futures:
            future.result()  # Wait for completion
    end_time = time.time()

    # Verify all operations completed successfully
    assert success_counter.value() == num_threads * operations_per_thread

    # Print performance stats
    duration = end_time - start_time
    ops_per_second = (num_threads * operations_per_thread) / duration
    print(
        f"Completed {num_threads * operations_per_thread} operations in {duration:.2f} seconds"
    )
    print(f"Performance: {ops_per_second:.2f} operations/second")

    # Ensure the cache size hasn't exceeded max_size
    assert cache.size() <= cache.max_size


# Only run this test when explicitly requested, as it's resource-intensive
@pytest.mark.skip(reason="Long-running stress test, run manually")
def test_stress_test_cache():
    """A longer-running stress test for the cache."""
    cache = ThreadSafeLRUCache(max_size=10000)
    num_threads = 50
    operations_per_thread = 10000

    # Set up tracking for successful operations
    success_counter = Counter()

    def worker(thread_id):
        for i in range(operations_per_thread):
            op = random.randint(0, 10)  # 0-8: read, 9-10: write
            # Use a slightly skewed distribution to create hot keys
            if random.random() < 0.2:  # 20% of the time, use a "hot" key
                key = f"hot_key_{random.randint(0, 50)}"
            else:
                key = f"key_{random.randint(0, 100000)}"

            if op < 8:  # 80% reads
                cache.get(key)
            else:  # 20% writes
                cache.put(key, f"value_{thread_id}_{i}")

            success_counter.increment()

    # Start threads
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for future in futures:
            future.result()  # Wait for completion
    end_time = time.time()

    # Verify all operations completed successfully
    assert success_counter.value() == num_threads * operations_per_thread

    # Print performance stats
    duration = end_time - start_time
    ops_per_second = (num_threads * operations_per_thread) / duration
    print(
        f"Stress test completed {num_threads * operations_per_thread} operations in {duration:.2f} seconds"
    )
    print(f"Performance: {ops_per_second:.2f} operations/second")

    # Ensure the cache size hasn't exceeded max_size
    assert cache.size() <= cache.max_size
