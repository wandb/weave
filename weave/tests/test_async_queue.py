import pytest
import asyncio
from ..async_queue import Queue, ProcessQueue, ThreadQueue
import threading
import aioprocessing


async def process_producer(queue: Queue) -> None:
    for i in range(3):
        print(f"Producer: {i}", flush=True)
        try:
            await queue.async_put(i)
        except NotImplementedError:
            queue.put(i)
        await asyncio.sleep(0.1)


def process_consumer(queue: Queue) -> None:
    async def _consume():
        for _ in range(3):
            try:
                item = await queue.async_get()
            except NotImplementedError:
                item = queue.get()
            print(f"Consumer: {item}", flush=True)
            queue.task_done()

    asyncio.run(_consume())


@pytest.mark.asyncio
async def test_async_process_queue_shared() -> None:
    queue: Queue = ProcessQueue()

    consumer_process = aioprocessing.AioProcess(target=process_consumer, args=(queue,))
    consumer_process.start()

    await process_producer(queue)
    await queue.async_join()
    consumer_process.join()


@pytest.mark.asyncio
async def test_async_thread_queue_shared() -> None:
    queue: Queue = ThreadQueue()
    consumer_thread = threading.Thread(target=process_consumer, args=(queue,))
    consumer_thread.start()

    await process_producer(queue)
    queue.join()
    consumer_thread.join()
