import asyncio
import random
import tempfile
from concurrent.futures import ThreadPoolExecutor

import PIL
import pytest


def get_image():
    # Create a temporary file that will be automatically cleaned up
    with tempfile.NamedTemporaryFile(suffix=".png") as temp_file:
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
    return image


def test_multiple_loads():
    """Test that loading an image multiple times works safely."""
    image = get_image()

    # Run 10 loads serially
    for _ in range(10):
        image.load()


# Repeat 5 times since we are trying to test for thread safety
@pytest.mark.parametrize("i", range(5))
def test_image_thread_safety(i):
    image = get_image()

    def load():
        """Load the image in a thread to avoid blocking the event loop"""
        for _ in range(10):
            image.load()

    with ThreadPoolExecutor(max_workers=10) as executor:
        jobs = [executor.submit(load) for i in range(10)]

    # Wait for all the threads to finish (will error if not thread safe)
    res = [job.result() for job in jobs]


@pytest.mark.asyncio
async def test_async_image_loading():
    """Test that loading an image directly from multiple async coroutines works safely.
    This test verifies that our locking works even with direct calls from async code."""
    image = get_image()

    async def load_async():
        await asyncio.sleep(0.1)
        for _ in range(10):
            image.load()

    # Run 10 concurrent loads
    tasks = [load_async() for _ in range(10)]
    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_async_thread_image_loading():
    """Test that loading an image safely from multiple async coroutines using to_thread.
    This test represents the recommended way to handle PIL operations in async code."""
    image = get_image()

    async def load_async():
        """Load the image in a thread to avoid blocking the event loop"""
        await asyncio.sleep(0.1)
        # Use to_thread to avoid blocking event loop with synchronous load()
        for _ in range(10):
            await asyncio.to_thread(image.load)

    # Run 10 concurrent loads
    tasks = [load_async() for _ in range(10)]
    await asyncio.gather(*tasks)
