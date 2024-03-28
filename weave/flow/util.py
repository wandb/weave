from typing import AsyncIterator, Callable, Iterable, Tuple, TypeVar, Awaitable
import asyncio

T = TypeVar("T")
U = TypeVar("U")


async def async_foreach(
    sequence: Iterable[T],
    func: Callable[[T], Awaitable[U]],
    max_concurrent_tasks: int,
) -> AsyncIterator[Tuple[T, U]]:
    semaphore = asyncio.Semaphore(max_concurrent_tasks)

    async def process_item(item: T) -> Tuple[T, U]:
        async with semaphore:
            result = await func(item)
            return item, result

    tasks = [asyncio.create_task(process_item(item)) for item in sequence]

    for task in asyncio.as_completed(tasks):
        item, result = await task
        yield item, result
