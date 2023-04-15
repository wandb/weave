import pytest
import asyncio
from typing import Any
from ..async_queue import BaseAsyncQueue, AsyncProcessQueue
import aioprocessing


async def process_producer(queue: BaseAsyncQueue, event: aioprocessing.Event) -> None:
    for i in range(3):
        print(f"Producer: {i}", flush=True)
        await queue.put(i)
        await asyncio.sleep(0.1)
    event.set()


def process_consumer(queue: BaseAsyncQueue, event: aioprocessing.Event) -> None:
    async def _consume():
        for _ in range(3):
            item = await queue.get()
            print(f"Consumer: {item}", flush=True)
            queue._queue.task_done()

    asyncio.run(_consume())


@pytest.mark.asyncio
async def test_async_process_queue_shared() -> None:
    queue: BaseAsyncQueue = AsyncProcessQueue()
    event = aioprocessing.Event()

    consumer_process = aioprocessing.AioProcess(
        target=process_consumer, args=(queue, event)
    )

    consumer_process.start()

    await process_producer(queue, event=event)
    await queue.join()
    await consumer_process.coro_join()
