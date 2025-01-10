# Two different implementations of an async map function that ensures
# no more than n tasks run in parallel. I did it two different ways to
# understand performance. Inconclusive. These are not used in the Weave
# code base right now.
# Exercise for read: Make these into async generators.

import asyncio
import typing


TaskInputType = typing.TypeVar("TaskInputType")
TaskOutputType = typing.TypeVar("TaskOutputType")


async def map_parallel_worker(
    task: typing.Callable[[TaskInputType], typing.Awaitable[TaskOutputType]],
    req_queue: asyncio.Queue[typing.Tuple[int, TaskInputType]],
    resp_queue: asyncio.Queue[typing.Tuple[int, TaskOutputType]],
) -> None:
    while True:
        item_index, item = await req_queue.get()
        resp = await task(item)
        await resp_queue.put((item_index, resp))


async def map_with_parallel_workers(
    items: typing.List[TaskInputType],
    task: typing.Callable[[TaskInputType], typing.Awaitable[TaskOutputType]],
    max_parallel: int = 100,
) -> typing.List[TaskOutputType]:
    req_queue: asyncio.Queue[typing.Tuple[int, TaskInputType]] = asyncio.Queue()
    resp_queue: asyncio.Queue[typing.Tuple[int, TaskOutputType]] = asyncio.Queue()

    resps: list[TaskOutputType] = [None] * len(items)  # type: ignore
    workers = []
    for i in range(max_parallel):
        workers.append(
            asyncio.create_task(map_parallel_worker(task, req_queue, resp_queue))
        )
    for i, item in enumerate(items):
        await req_queue.put((i, item))

    for i in range(len(items)):
        item_index, resp = await resp_queue.get()
        resps[item_index] = resp

    for worker in workers:
        worker.cancel()

    return resps


async def map_n_live_task_worker(
    task: typing.Callable[[TaskInputType], typing.Awaitable[TaskOutputType]],
    item_index: int,
    item: TaskInputType,
    resp_queue: asyncio.Queue[typing.Tuple[int, TaskOutputType]],
) -> None:
    resp = await task(item)
    await resp_queue.put((item_index, resp))


async def map_with_n_live_tasks(
    items: typing.List[TaskInputType],
    task: typing.Callable[[TaskInputType], typing.Awaitable[TaskOutputType]],
    max_parallel: int = 100,
) -> typing.List[TaskOutputType]:
    resp_queue: asyncio.Queue[typing.Tuple[int, TaskOutputType]] = asyncio.Queue()

    running = 0
    next_item_index = 0
    resps: list[TaskOutputType] = [None] * len(items)  # type: ignore
    while next_item_index < len(items) or running > 0:
        if running < max_parallel and next_item_index < len(items):
            item = items[next_item_index]
            asyncio.create_task(
                map_n_live_task_worker(task, next_item_index, item, resp_queue)
            )
            next_item_index += 1
            if next_item_index % 100 == 0:
                print("next_item_index", next_item_index, "running", running)
            running += 1
        else:
            idx, resp = await resp_queue.get()
            resps[idx] = resp
            running -= 1

    return resps
