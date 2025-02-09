import datetime
import os
import random
import tempfile
import time
from typing import Any

import PIL

import weave
from tests.conftest import CachingMiddlewareTraceServer
from weave.tsi.trace_server_interface import (
    ObjReadReq,
    ObjReadRes,
    ObjSchema,
    TraceServerInterface,
)


def create_random_pil_image():
    im = PIL.Image.new("RGB", (100, 100), color=(255, 255, 255))
    for i in range(100):
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
    for row1, row2 in zip(rows1, rows2):
        compare_images(row1["image"], row2["image"])
        assert row1["label"] == row2["label"]


def test_server_caching(client):
    dataset = weave.Dataset(rows=create_dataset_rows(5))
    ref = weave.publish(dataset)

    recording_caching_server = client.server
    caching_server: CachingMiddlewareTraceServer = recording_caching_server.server

    # First call should miss
    caching_server.reset_cache_recorder()
    gotten_dataset = client.get(ref)
    assert caching_server.get_cache_recorder() == {
        "hits": 0,
        # 1 obj read for the dataset
        # 1 table read for the rows
        # 5 images
        "misses": 7,
        "errors": 0,
        "skips": 0,
    }
    compare_datasets(gotten_dataset, dataset)

    # Second call should hit
    caching_server.reset_cache_recorder()
    compare_datasets(client.get(ref), dataset)
    assert caching_server.get_cache_recorder() == {
        "hits": 8,
        "misses": 0,
        "errors": 0,
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
        "errors": 0,
        "skips": 8,
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
            assert caching_server._cache.volume() <= limit * 1.1

            # Allows us to test the on-disk size
            sizes = get_cache_sizes(temp_dir)
            assert len(sizes) == 3
            assert sizes["cache.db-shm"] <= 50000
            assert sizes["cache.db-wal"] < 4_000_000 * 1.1  # WAL bound by 4MB
            assert sizes["cache.db"] <= limit * 1.1
            print(sizes)

        # Assert that the WAL file is removed when the server is deleted
        del caching_server
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

    assert added_latency < 0.001
