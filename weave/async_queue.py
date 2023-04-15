import asyncio
import aioprocessing
from typing import Any, Generic, TypeVar

QueueItemType = TypeVar("QueueItemType")


class BaseAsyncQueue(Generic[QueueItemType]):
    async def put(self, item: QueueItemType) -> None:
        raise NotImplementedError

    async def get(self) -> QueueItemType:
        raise NotImplementedError

    async def join(self) -> None:
        raise NotImplementedError

    def task_done(self) -> None:
        raise NotImplementedError


class AsyncProcessQueue(BaseAsyncQueue, Generic[QueueItemType]):
    def __init__(self, maxsize: int = 0):
        self._queue: aioprocessing.Queue = aioprocessing.AioJoinableQueue(
            maxsize=maxsize
        )

    async def put(self, item: QueueItemType) -> None:
        await self._queue.coro_put(item)

    async def get(self) -> QueueItemType:
        return await self._queue.coro_get()

    async def join(self) -> None:
        await self._queue.coro_join()

    def task_done(self) -> None:
        self._queue.task_done()


AsyncThreadQueue = AsyncProcessQueue
