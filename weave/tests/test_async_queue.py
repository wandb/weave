import pytest
import asyncio
from ..async_queue import BaseAsyncQueue, AsyncProcessQueue, AsyncThreadQueue
import threading
import aioprocessing


async def process_producer(queue: BaseAsyncQueue) -> None:
    for i in range(3):
        print(f"Producer: {i}", flush=True)
        await queue.put(i)
        await asyncio.sleep(0.1)


def process_consumer(queue: BaseAsyncQueue) -> None:
    async def _consume():
        for _ in range(3):
            item = await queue.get()
            print(f"Consumer: {item}", flush=True)
            queue.task_done()

    asyncio.run(_consume())


@pytest.mark.asyncio
async def test_async_process_queue_shared() -> None:
    queue: BaseAsyncQueue = AsyncProcessQueue()

    consumer_process = aioprocessing.AioProcess(target=process_consumer, args=(queue,))
    consumer_process.start()

    await process_producer(queue)
    await queue.join()
    consumer_process.join()


@pytest.mark.asyncio
async def test_async_thread_queue_shared() -> None:
    queue: BaseAsyncQueue = AsyncThreadQueue()
    consumer_thread = threading.Thread(target=process_consumer, args=(queue,))
    consumer_thread.start()

    await process_producer(queue)
    await queue.join()
    consumer_thread.join()
