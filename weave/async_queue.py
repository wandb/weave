import asyncio
import aioprocessing
from typing import Any, Generic, TypeVar

QueueItemType = TypeVar("QueueItemType")


class BaseAsyncQueue(Generic[QueueItemType]):
    async def put(self, item: QueueItemType) -> None:
        raise NotImplementedError

    async def get(self) -> QueueItemType:
        raise NotImplementedError

    async def task_done(self) -> None:
        raise NotImplementedError

    async def join(self) -> None:
        raise NotImplementedError

    async def qsize(self) -> int:
        raise NotImplementedError


class AsyncThreadQueue(BaseAsyncQueue, Generic[QueueItemType]):
    def __init__(self, maxsize: int = 0):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)

    async def put(self, item: QueueItemType) -> None:
        await self._queue.put(item)

    async def get(self) -> QueueItemType:
        item = await self._queue.get()
        return item

    async def task_done(self) -> None:
        self._queue.task_done()

    async def join(self) -> None:
        await self._queue.join()

    async def qsize(self) -> int:
        return self._queue.qsize()


class AsyncProcessQueue(BaseAsyncQueue, Generic[QueueItemType]):
    def __init__(self, maxsize: int = 0):
        self._queue: aioprocessing.Queue = aioprocessing.AioQueue(maxsize=maxsize)

    async def put(self, item: QueueItemType) -> None:
        await self._queue.coro_put(item)

    async def get(self) -> QueueItemType:
        return await self._queue.coro_get()

    async def task_done(self) -> None:
        await self._queue.coro_task_done()

    async def join(self) -> None:
        await self._queue.coro_join()

    async def qsize(self) -> int:
        return await self._queue.coro_qsize()
