import atexit
import aioprocessing
import janus
from typing import Optional, Generic, TypeVar
import asyncio

QueueItemType = TypeVar("QueueItemType")


class Queue(Generic[QueueItemType]):
    async def async_put(self, item: QueueItemType) -> None:
        raise NotImplementedError

    async def async_get(
        self,
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
        self,
    ) -> QueueItemType:
        return await self._queue.coro_get()

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
    def queue(self) -> janus.Queue:
        if not hasattr(self, "_queue"):
            self.init()
        return self._queue

    def __init__(
        self,
        maxsize: int = 0,
    ):
        self.maxsize = maxsize

    async def async_put(self, item: QueueItemType) -> None:
        await self.queue.async_q.put(item)

    async def async_get(self) -> QueueItemType:
        return await self.queue.async_q.get()

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

    def init(self) -> None:
        """
        This is some old code that previously just has one line:
        `self._queue: janus.Queue = janus.Queue(maxsize=self.maxsize)`

        However, `init` is not `async` and therefore cannot sure we are in the event loop.
        Moreover, these objects are created and stored globally! There are some race cases
        where the event loop is not running when the object is created. This is a super
        hack to avoid a huge refactor and instead, just create a new event loop and set it
        as the current event loop. When the janus.Queue is created, it internally maintains
        a reference to the event loop that was current when it was created. This means
        that we cannot immediately close it. Instead, we register a function to close it at  
        the end of the program.

        This is a hack and should be removed when possible.
        """
        not_in_event_loop = not _in_event_loop()
        if not_in_event_loop:
            # Yikes! we are going to do something hacky:
            if not hasattr(self, "_local_loop"):
                self._local_loop = asyncio.new_event_loop()
                atexit.register(self._local_loop.close)
            asyncio.set_event_loop(self._local_loop)
        self._queue: janus.Queue = janus.Queue(maxsize=self.maxsize)
        if not_in_event_loop:
            asyncio.set_event_loop(None)

def _in_event_loop() -> bool:
    try:
        return asyncio.get_event_loop().is_running()
    except RuntimeError:
        return False