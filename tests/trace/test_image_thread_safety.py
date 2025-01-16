import os
import random
from concurrent.futures import ThreadPoolExecutor

import PIL
import pytest


@pytest.fixture()
def deferred_cleanup():
    files_to_cleanup = []

    def add_file(name: str):
        files_to_cleanup.append(name)

    def cleanup():
        for name in files_to_cleanup:
            os.remove(name)

    try:
        yield add_file
    finally:
        cleanup()


# Repeat 5 times since we are trying to test for thread safety
@pytest.mark.parametrize("i", range(5))
def test_image_thread_safety(deferred_cleanup, i):
    file_name = f"temp_test_{i}.png"

    # 1. Create a random in-memory image
    image = PIL.Image.new("RGB", (1024, 1024))
    image.putdata(
        [
            (
                int(255 * random.random()),
                int(255 * random.random()),
                int(255 * random.random()),
            )
            for _ in range(1024 * 1024)
        ]
    )

    # 2. Save the image to a file
    deferred_cleanup(file_name)  # Cleanup the file on exit
    image.save(file_name)

    # 3. Open the image in multiple threads and load it
    # This simulates what can happen when users are working
    # with images across threads.
    image = PIL.Image.open(file_name)
    with ThreadPoolExecutor(max_workers=10) as executor:
        jobs = [executor.submit(image.load) for i in range(10)]

    # Wait for all the threads to finish
    res = [job.result() for job in jobs]
