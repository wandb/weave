import time
import asyncio
import queue
import aioprocessing
from typing import Optional, Generic, TypeVar

QueueItemType = TypeVar("QueueItemType")

POLL_INTERVAL = 1e-3  # sec


class Queue(Generic[QueueItemType]):
    async def async_put(self, item: QueueItemType) -> None:
        raise NotImplementedError

    async def async_get(
        self, block: bool = True, timeout: Optional[int] = None
    ) -> QueueItemType:
        raise NotImplementedError

    async def async_join(self) -> None:
        raise NotImplementedError

    def task_done(self) -> None:
        raise NotImplementedError

    def put(self, item: QueueItemType) -> None:
        raise NotImplementedError

    def get(self, block: bool = True, timeout: Optional[int] = None) -> QueueItemType:
        raise NotImplementedError

    def join(self) -> None:
        raise NotImplementedError


class ProcessQueue(Queue, Generic[QueueItemType]):
    def __init__(self, maxsize: int = 0):
        self._queue: aioprocessing.Queue = aioprocessing.AioJoinableQueue(
            maxsize=maxsize
        )

    async def async_put(self, item: QueueItemType) -> None:
        await self._queue.coro_put(item)

    async def async_get(
        self, block: bool = True, timeout: Optional[int] = None
    ) -> QueueItemType:
        return await self._queue.coro_get(block=block, timeout=timeout)

    async def async_join(self) -> None:
        await self._queue.coro_join()

    def put(self, item: QueueItemType) -> None:
        self._queue.put(item)

    def get(self, block: bool = True, timeout: Optional[int] = None) -> QueueItemType:
        return self._queue.get(block=block, timeout=timeout)

    def join(self) -> None:
        self._queue.join()

    def task_done(self) -> None:
        self._queue.task_done()


class ThreadQueue(Queue, Generic[QueueItemType]):
    def __init__(self, maxsize: int = 0):
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)

    async def async_put(self, item: QueueItemType) -> None:
        self.put(item)

    async def async_get(
        self, block: bool = True, timeout: Optional[int] = None
    ) -> QueueItemType:
        # approximate async with polling every microsec
        start = time.time()
        while True:
            try:
                item = self.get(block=False)
            except (asyncio.queues.QueueEmpty, queue.Empty):
                if not block:
                    raise
                await asyncio.sleep(POLL_INTERVAL)
                if timeout is not None and time.time() - start > timeout:
                    raise TimeoutError
                continue
            return item

    async def async_join(self) -> None:
        self.join()

    def put(self, item: QueueItemType) -> None:
        self._queue.put(item)

    def get(self, block: bool = True, timeout: Optional[int] = None) -> QueueItemType:
        return self._queue.get(block=block, timeout=timeout)

    def join(self) -> None:
        self._queue.join()

    def task_done(self) -> None:
        self._queue.task_done()
