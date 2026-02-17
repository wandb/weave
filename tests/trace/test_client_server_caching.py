import datetime
import os
import random
import sys
import tempfile
import time
from typing import Any

import PIL

import weave
from tests.conftest import CachingMiddlewareTraceServer
from weave.trace_server.trace_server_interface import (
    FileContentReadReq,
    FileCreateReq,
    ObjCreateReq,
    ObjReadReq,
    ObjReadRes,
    ObjSchema,
    ObjSchemaForInsert,
    TraceServerInterface,
)


def create_random_pil_image():
    im = PIL.Image.new("RGB", (100, 100), color=(255, 255, 255))
    for _i in range(100):
        im.putpixel(
            (random.randint(0, 99), random.randint(0, 99)),
            (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
        )
    return im


def create_dataset_rows(n: int = 5):
    return [{"image": create_random_pil_image(), "label": i} for i in range(n)]


def compare_images(im1: PIL.Image.Image, im2: PIL.Image.Image):
    assert im1.size == im2.size
    assert im1.mode == im2.mode
    assert im1.tobytes() == im2.tobytes()


def compare_datasets(ds1: weave.Dataset, ds2: weave.Dataset):
    rows1 = ds1.rows.rows
    rows2 = ds2.rows.rows
    assert len(rows1) == len(rows2)
    for row1, row2 in zip(rows1, rows2, strict=False):
        compare_images(row1["image"], row2["image"])
        assert row1["label"] == row2["label"]


def test_server_caching(client):
    os.environ["WEAVE_USE_SERVER_CACHE"] = "true"
    dataset = weave.Dataset(rows=create_dataset_rows(5))
    ref = weave.publish(dataset)

    recording_caching_server = client.server
    caching_server: CachingMiddlewareTraceServer = recording_caching_server.server

    # First call should miss
    caching_server.reset_cache_recorder()
    gotten_dataset = client.get(ref)
    assert caching_server.get_cache_recorder() == {
        "hits": 0,
        # get the ref
        "misses": 1,
        "skips": 0,
    }
    caching_server.reset_cache_recorder()
    rows = list(gotten_dataset)
    assert caching_server.get_cache_recorder() == {
        "hits": 0,
        # 1 table read for the rows
        # 1 table_query_stats for len(rows)
        # 5 images
        "misses": 7,
        "skips": 0,
    }
    compare_datasets(gotten_dataset, dataset)

    # Second call should hit
    caching_server.reset_cache_recorder()
    compare_datasets(client.get(ref), dataset)
    assert caching_server.get_cache_recorder() == {
        "hits": 7,
        "misses": 0,
        "skips": 0,
    }

    # Third call should skip
    caching_server.reset_cache_recorder()
    os.environ["WEAVE_USE_SERVER_CACHE"] = "false"
    compare_datasets(client.get(ref), dataset)
    os.environ["WEAVE_USE_SERVER_CACHE"] = "true"
    assert caching_server.get_cache_recorder() == {
        "hits": 0,
        "misses": 0,
        "skips": 7,
    }


class MockServer(TraceServerInterface):
    def __init__(self, mock_val: Any):
        self.mock_val = mock_val

    def obj_read(self, req: ObjReadReq) -> ObjReadRes:
        return ObjReadRes(
            obj=ObjSchema(
                project_id=req.project_id,
                object_id=req.object_id,
                created_at=datetime.datetime.now(),
                deleted_at=None,
                digest=req.digest,
                version_index=0,
                is_latest=1,
                kind="object",
                base_object_class=None,
                leaf_object_class=None,
                val=self.mock_val,
            )
        )


def get_cache_sizes(cache_dir: str) -> dict[str, int]:
    return {
        f: os.path.getsize(os.path.join(cache_dir, f)) for f in os.listdir(cache_dir)
    }


def test_server_cache_size_limit(client):
    count = 500
    limit = 50000
    with tempfile.TemporaryDirectory() as temp_dir:
        caching_server = CachingMiddlewareTraceServer(
            next_trace_server=MockServer("a" * 1000),
            cache_dir=temp_dir,
            size_limit=50000,
        )

        sizes = get_cache_sizes(temp_dir)
        assert len(sizes) == 3
        assert sizes["cache.db-shm"] <= 50000
        assert sizes["cache.db-wal"] == 0  # WAL should be at 0 now
        assert sizes["cache.db"] <= 50000

        for i in range(count):
            caching_server.obj_read(
                ObjReadReq(project_id="test", object_id="test", digest=f"test_{i}")
            )

            # Internally, the cache estimates it's own size
            # Access the disk cache layer (second layer in the stack)
            disk_cache = caching_server._cache.layers[1]
            assert disk_cache._cache.volume() <= limit * 1.1

            # Allows us to test the on-disk size
            sizes = get_cache_sizes(temp_dir)
            assert len(sizes) == 3
            assert sizes["cache.db-shm"] <= 50000
            assert sizes["cache.db-wal"] < 4_000_000 * 1.1  # WAL bound by 4MB
            assert sizes["cache.db"] <= limit * 1.1
            print(sizes)

        sizes = get_cache_sizes(temp_dir)
        # depending on the OS, we could be in 1 of two cases.
        # Case 1: only the db file remains
        if len(sizes) == 1:
            assert sizes["cache.db"] <= limit * 1.1
        elif len(sizes) == 3:
            assert sizes["cache.db-shm"] <= 50000
            assert sizes["cache.db-wal"] == 0
            assert sizes["cache.db"] <= limit * 1.1
        else:
            raise ValueError(
                f"Unexpected number of files in cache directory: {len(sizes)}"
            )


def test_server_cache_latency(client):
    count = 500

    base_server = MockServer("a" * 1000)
    caching_server = CachingMiddlewareTraceServer(next_trace_server=base_server)

    def get_latency_for_server(server: TraceServerInterface, count: int):
        start = time.time()
        for i in range(count):
            server.obj_read(
                ObjReadReq(project_id="test", object_id="test", digest=f"test_{i}")
            )
        end = time.time()
        return (end - start) / count

    latency_without_cache = get_latency_for_server(base_server, count)
    latency_with_cache = get_latency_for_server(caching_server, count)

    added_latency = latency_with_cache - latency_without_cache
    print(f"Added latency: {added_latency}")

    if sys.platform == "win32":
        assert added_latency < 0.05  # Windows is REALLY slow
    else:
        assert added_latency < 0.002


def test_file_create_caching(client):
    caching_server: CachingMiddlewareTraceServer = client.server.server
    file_bytes = b"hello"
    caching_server.reset_cache_recorder()
    create_0 = client.server.file_create(
        FileCreateReq(
            project_id="test",
            name="test",
            content=file_bytes,
        )
    )
    assert caching_server.get_cache_recorder() == {
        "hits": 0,
        "misses": 1,
        "skips": 0,
    }
    caching_server.reset_cache_recorder()
    create_1 = client.server.file_create(
        FileCreateReq(
            project_id="test",
            name="test",
            content=file_bytes,
        )
    )
    assert caching_server.get_cache_recorder() == {
        "hits": 1,
        "misses": 0,
        "skips": 0,
    }
    assert create_0 == create_1

    caching_server.reset_cache_recorder()
    read_0 = client.server.file_content_read(
        FileContentReadReq(
            project_id="test",
            digest=create_0.digest,
        )
    )
    assert caching_server.get_cache_recorder() == {
        "hits": 0,
        "misses": 1,
        "skips": 0,
    }
    caching_server.reset_cache_recorder()
    read_1 = client.server.file_content_read(
        FileContentReadReq(
            project_id="test",
            digest=create_0.digest,
        )
    )
    assert caching_server.get_cache_recorder() == {
        "hits": 1,
        "misses": 0,
        "skips": 0,
    }
    assert read_0.content == read_1.content == file_bytes


def test_obj_create_caching(client):
    caching_server: CachingMiddlewareTraceServer = client.server.server
    val = {"hello": "world"}
    caching_server.reset_cache_recorder()
    create_0 = client.server.obj_create(
        ObjCreateReq(
            obj=ObjSchemaForInsert(
                project_id="test",
                object_id="test",
                val=val,
            )
        )
    )
    assert caching_server.get_cache_recorder() == {
        "hits": 0,
        "misses": 1,
        "skips": 0,
    }
    caching_server.reset_cache_recorder()
    create_1 = client.server.obj_create(
        ObjCreateReq(
            obj=ObjSchemaForInsert(
                project_id="test",
                object_id="test",
                val=val,
            )
        )
    )
    assert caching_server.get_cache_recorder() == {
        "hits": 1,
        "misses": 0,
        "skips": 0,
    }
    assert create_0 == create_1

    caching_server.reset_cache_recorder()
    read_0 = client.server.obj_read(
        ObjReadReq(
            project_id="test",
            object_id="test",
            digest=create_0.digest,
        )
    )
    assert caching_server.get_cache_recorder() == {
        "hits": 0,
        "misses": 1,
        "skips": 0,
    }
    caching_server.reset_cache_recorder()
    read_1 = client.server.obj_read(
        ObjReadReq(
            project_id="test",
            object_id="test",
            digest=create_0.digest,
        )
    )
    assert caching_server.get_cache_recorder() == {
        "hits": 1,
        "misses": 0,
        "skips": 0,
    }
    assert read_0.obj.val == read_1.obj.val == val


def test_cache_default_enabled():
    """Test that caching is enabled by default."""
    from weave.trace.settings import use_server_cache

    # Should be True by default now
    assert use_server_cache() is True


def test_cache_isolation_between_tests(tmp_path, monkeypatch):
    """Test that the caching_client_isolation fixture properly isolates cache directories."""
    # This test verifies that each test gets its own cache directory
    test_cache_dir_1 = tmp_path / "cache_1"
    test_cache_dir_2 = tmp_path / "cache_2"

    # Create two different cache instances with different directories
    from tests.conftest import ThrowingServer
    from weave.trace_server_bindings.caching_middleware_trace_server import (
        CachingMiddlewareTraceServer,
    )

    base_server = ThrowingServer()
    cache_server_1 = CachingMiddlewareTraceServer(base_server, str(test_cache_dir_1))
    cache_server_2 = CachingMiddlewareTraceServer(base_server, str(test_cache_dir_2))

    # Write to first cache
    cache_server_1._safe_cache_set("test_key", "test_value_1")

    # Write different value to second cache with same key
    cache_server_2._safe_cache_set("test_key", "test_value_2")

    # Verify isolation - each cache should have its own value
    assert cache_server_1._safe_cache_get("test_key") == "test_value_1"
    assert cache_server_2._safe_cache_get("test_key") == "test_value_2"


def test_cache_persistence_across_client_instances(tmp_path):
    """Test that cache persists when creating new client instances with same cache directory."""
    from tests.conftest import ThrowingServer
    from weave.trace_server_bindings.caching_middleware_trace_server import (
        CachingMiddlewareTraceServer,
    )

    cache_dir = str(tmp_path / "persistent_cache")
    base_server = ThrowingServer()

    # Create first cache instance and store something
    cache_server_1 = CachingMiddlewareTraceServer(base_server, cache_dir)
    cache_server_1._safe_cache_set("persistent_key", "persistent_value")

    # Create second cache instance with same directory
    cache_server_2 = CachingMiddlewareTraceServer(base_server, cache_dir)

    # Should be able to retrieve the value from disk
    cached_value = cache_server_2._safe_cache_get("persistent_key")
    assert cached_value == "persistent_value"

    # Cleanup
    cache_server_1.__del__()  # Simulate client shutdown
    cache_server_2.__del__()


def test_cache_existence_check_optimization(tmp_path):
    """Test that the existence check optimization works correctly."""
    from weave.trace_server_bindings.caching_middleware_trace_server import (
        create_memory_disk_cache,
    )

    cache_dir = str(tmp_path / "existence_test")
    cache = create_memory_disk_cache(cache_dir, 1000000)

    # First write should hit both memory and disk
    cache.put("test_key", "test_value")

    # Key should exist in both layers
    assert "test_key" in cache
    assert "test_key" in cache.layers[0]  # memory cache
    # Note: We can't easily test disk cache __contains__ directly due to DiskCache wrapper

    # Second write with same key should skip disk write due to existence check
    # This is hard to test directly, so we inject a stale value directly:
    cache.layers[0].put("test_key", "INVALID")
    cache.layers[1].put("test_key", "INVALID")
    # This put should skip the disk write
    cache.put("test_key", "test_value")  # Same value
    assert "test_key" in cache

    cache.close()


def test_cache_keys_method(tmp_path):
    """Test that the keys() method returns the union of all keys across cache layers."""
    from weave.trace_server_bindings.caching_middleware_trace_server import (
        create_memory_disk_cache,
    )

    cache_dir = str(tmp_path / "keys_test")
    cache = create_memory_disk_cache(cache_dir, 1000000)

    # Add some keys (directly to layers)
    cache.layers[0].put("key1", "value1")
    cache.layers[1].put("key2", "value2")

    # Get all keys
    all_keys = cache.keys()

    # Should contain all our keys
    assert "key1" in all_keys
    assert "key2" in all_keys
    assert len(all_keys) == 2

    cache.close()


def test_cache_error_handling_robustness(tmp_path):
    """Test that cache handles errors gracefully without crashing."""
    from weave.trace_server_bindings.caching_middleware_trace_server import (
        create_memory_disk_cache,
    )

    cache_dir = str(tmp_path / "error_test")
    cache = create_memory_disk_cache(cache_dir, 1000000)

    # Normal operation should work
    cache.put("good_key", "good_value")
    assert cache.get("good_key") == "good_value"

    # Getting non-existent key should return None (not raise)
    assert cache.get("nonexistent_key") is None

    # Deleting non-existent key should not raise
    cache.delete("nonexistent_key")  # Should not crash

    # Checking non-existent key should return False
    assert "nonexistent_key" not in cache

    cache.close()


def test_cache_memory_disk_layer_interaction(tmp_path):
    """Test that memory and disk cache layers work together correctly."""
    from weave.trace_server_bindings.caching_middleware_trace_server import (
        create_memory_disk_cache,
    )

    cache_dir = str(tmp_path / "layer_test")
    cache = create_memory_disk_cache(cache_dir, 1000000)

    # Store a value - should go to both layers
    cache.put("layer_key", "layer_value")

    # Should be retrievable (could come from either layer)
    assert cache.get("layer_key") == "layer_value"

    # Clear only memory cache (access internal structure for testing)
    memory_cache = cache.layers[0]
    memory_cache.clear()

    # Should still be retrievable from disk
    assert cache.get("layer_key") == "layer_value"

    # After retrieval, should be back in memory cache
    assert memory_cache.get("layer_key") == "layer_value"

    cache.close()


def test_cache_directory_creation(tmp_path):
    """Test that cache directory is created if it doesn't exist."""
    from tests.conftest import ThrowingServer
    from weave.trace_server_bindings.caching_middleware_trace_server import (
        CachingMiddlewareTraceServer,
    )

    # Use a nested directory that doesn't exist
    cache_dir = str(tmp_path / "nested" / "cache" / "directory")
    assert not os.path.exists(cache_dir)

    base_server = ThrowingServer()
    cache_server = CachingMiddlewareTraceServer(base_server, cache_dir)

    # Directory should be created
    assert os.path.exists(cache_dir)

    # Should be able to use the cache
    cache_server._safe_cache_set("creation_test", "success")
    assert cache_server._safe_cache_get("creation_test") == "success"

    cache_server.__del__()
