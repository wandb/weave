import os
import random

import PIL

import weave
from tests.conftest import CachingMiddlewareTraceServer


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
    caching_server.reset_cache_recorder()
    compare_datasets(client.get(ref), dataset)
    assert caching_server.get_cache_recorder() == {
        "hits": 1,
        "misses": 7,
        "errors": 0,
        "skips": 0,
    }

    caching_server.reset_cache_recorder()
    compare_datasets(client.get(ref), dataset)
    assert caching_server.get_cache_recorder() == {
        "hits": 8,
        "misses": 0,
        "errors": 0,
        "skips": 0,
    }

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
