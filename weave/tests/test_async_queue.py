import pytest
import asyncio
from typing import Any
from ..async_queue import BaseAsyncQueue, AsyncThreadQueue, AsyncProcessQueue
import aioprocessing
import multiprocessing


def process_producer(queue: BaseAsyncQueue) -> None:
    async def producer() -> None:
        for i in range(3):
            print(f"Producer: {i}")
            await queue.put(i)
            await asyncio.sleep(0.1)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(producer())


def process_consumer(queue: BaseAsyncQueue) -> None:
    async def consumer() -> None:
        while not (await queue.qsize()) == 0:
            item = await queue.get()
            print(f"Consumer: {item}")
            await queue.task_done()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(consumer())


@pytest.mark.asyncio
async def test_async_process_queue_shared() -> None:
    queue: BaseAsyncQueue = AsyncProcessQueue()
    event = aioprocessing.Event()

    producer_process = aioprocessing.AioProcess(target=process_producer, args=(queue,))
    consumer_process = aioprocessing.AioProcess(target=process_consumer, args=(queue,))

    producer_process.start()
    consumer_process.start()

    producer_process.join()
    consumer_process.join()

    # await queue.join()
