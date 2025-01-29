import random

import PIL

import weave


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

    compare_datasets(client.get(ref), dataset)
    compare_datasets(client.get(ref), dataset)
    compare_datasets(client.get(ref), dataset)
