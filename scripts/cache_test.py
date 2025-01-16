import random
import time

import PIL

import weave

weave.init("cache_test")


def make_random_image(width: int, height: int) -> PIL.Image:
    image = PIL.Image.new("RGB", (width, height))
    image.putdata(
        [
            (
                int(255 * random.random()),
                int(255 * random.random()),
                int(255 * random.random()),
            )
            for _ in range(width * height)
        ]
    )
    return image


def make_random_dataset(num_rows: int) -> weave.Dataset:
    # Create the dataset
    rows = [
        {
            "id": i,
            "image_0": make_random_image(1024, 1024),
            "truth": i % 2,
        }
        for i in range(5)
    ]

    return weave.Dataset(rows=rows)


def do_experiment():
    ref = weave.publish(make_random_dataset(10), "test_dataset")
    uri_str = ref.uri()
    ds_ref = weave.ref(uri_str)

    for i in range(3):
        clock = time.perf_counter()
        ds = ds_ref.get()
        print(f"Got dataset {i} in {time.perf_counter() - clock} seconds")
        clock = time.perf_counter()
        images = [r["image_0"] for r in ds.rows]
        print(f"Got {len(images)} images in {time.perf_counter() - clock} seconds")


do_experiment()

print("Changing")

import os

os.environ["WEAVE_USE_SERVER_CACHE"] = "false"

do_experiment()
