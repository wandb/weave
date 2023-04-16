import aioprocessing
import janus
from typing import Optional, Generic, TypeVar

QueueItemType = TypeVar("QueueItemType")


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
    @property
    def queue(self):
        if self._queue is None:
            self._queue: janus.AsyncQueue[QueueItemType] = janus.Queue(
                maxsize=self.maxsize
            )
        return self._queue

    def __init__(self, maxsize: int = 0):
        self._queue = None
        self.maxsize = maxsize

    async def async_put(self, item: QueueItemType) -> None:
        await self.queue.async_q.put(item)

    async def async_get(
        self, block: bool = True, timeout: Optional[int] = None
    ) -> QueueItemType:
        if timeout is not None:
            raise NotImplementedError
        if block:
            return await self.queue.async_q.get()
        return self.queue.async_q.get_nowait()

    async def async_join(self) -> None:
        await self.queue.async_q.join()

    def put(self, item: QueueItemType) -> None:
        self.queue.sync_q.put(item)

    def get(self, block: bool = True, timeout: Optional[int] = None) -> QueueItemType:
        return self.queue.sync_q.get(block=block, timeout=timeout)

    def join(self) -> None:
        self.queue.sync_q.join()

    def task_done(self) -> None:
        self.queue.sync_q.task_done()
