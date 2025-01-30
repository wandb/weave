import random
import tempfile
from concurrent.futures import ThreadPoolExecutor

import PIL
import pytest


# Repeat 5 times since we are trying to test for thread safety
@pytest.mark.parametrize("i", range(5))
def test_image_thread_safety(i):
    # Create a temporary file that will be automatically cleaned up
    with tempfile.NamedTemporaryFile(suffix=".png") as temp_file:
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
        image.save(temp_file.name)

        # 3. Open the image in multiple threads and load it
        # This simulates what can happen when users are working
        # with images across threads.
        image = PIL.Image.open(temp_file.name)
        with ThreadPoolExecutor(max_workers=10) as executor:
            jobs = [executor.submit(image.load) for i in range(10)]

        # Wait for all the threads to finish
        res = [job.result() for job in jobs]
