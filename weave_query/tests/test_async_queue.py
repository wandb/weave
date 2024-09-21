import asyncio
import threading

import aioprocessing
import pytest

from weave.legacy.weave.async_queue import ProcessQueue, Queue, ThreadQueue


async def process_producer(queue: Queue) -> None:
    tasks = set()
    loop = asyncio.get_running_loop()
    for i in range(3):
        print(f"Producer: {i}", flush=True)
        task = loop.create_task(queue.async_put(i))
        tasks.add(task)
    await asyncio.wait(tasks)


def process_consumer(queue: Queue) -> None:
    async def _consume():
        for _ in range(3):
            if isinstance(queue, ThreadQueue):
                item = queue.get()
            else:
                item = await queue.async_get()
            print(f"Consumer: {item}", flush=True)
            queue.task_done()

    asyncio.run(_consume())


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_async_process_queue_shared() -> None:
    queue: Queue = ProcessQueue()

    consumer_process = aioprocessing.AioProcess(target=process_consumer, args=(queue,))
    consumer_process.start()

    await process_producer(queue)

    queue.join()
    consumer_process.join()


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_async_thread_queue_shared() -> None:
    queue: Queue = ThreadQueue()
    consumer_thread = threading.Thread(target=process_consumer, args=(queue,))
    consumer_thread.start()

    await process_producer(queue)
    queue.join()
    consumer_thread.join()
