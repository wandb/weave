import atexit
import logging
import time
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from typing import Callable, Generic, TypeVar

from weave.trace.context.tests_context import get_raise_on_captured_errors

T = TypeVar("T")
logger = logging.getLogger(__name__)


class AsyncBatchProcessor(Generic[T]):
    """A class that asynchronously processes batches of items using a provided processor function."""

    def __init__(
        self,
        processor_fn: Callable[[list[T]], None],
        max_batch_size: int = 100,
        min_batch_interval: float = 1.0,
        max_queue_size: int = 10_000,
    ) -> None:
        """
        Initializes an instance of AsyncBatchProcessor.

        Args:
            processor_fn (Callable[[list[T]], None]): The function to process the batches of items.
            max_batch_size (int, optional): The maximum size of each batch. Defaults to 100.
            min_batch_interval (float, optional): The minimum interval between processing batches. Defaults to 1.0.
            max_queue_size (int, optional): The maximum number of items to hold in the queue. Defaults to 10_000.  0 means no limit.
        """
        self.processor_fn = processor_fn
        self.max_batch_size = max_batch_size
        self.min_batch_interval = min_batch_interval
        self.queue: Queue[T] = Queue(maxsize=max_queue_size)
        self.lock = Lock()
        self.stop_accepting_work_event = Event()
        self.processing_thread = Thread(target=self._process_batches)
        self.processing_thread.daemon = True
        self.processing_thread.start()

        # TODO: Probably should include a health check thread here.  It will revive the
        # processing thread if that thread dies.

        # TODO: Probably should include some sort of local write buffer.  It might not need
        # to be here, but it should exist.  That handles 2 cases:
        # 1. The queue is full, so users can sync up data later.
        # 2. The system crashes for some reason, so users can resume from the local buffer.

        atexit.register(self.stop_accepting_new_work_and_flush_queue)

    @property
    def num_outstanding_jobs(self) -> int:
        """Returns the number of items currently in the queue."""
        with self.lock:
            return self.queue.qsize()

    def enqueue(self, items: list[T]) -> None:
        """
        Enqueues a list of items to be processed.

        Args:
            items (list[T]): The items to be processed.
        """
        with self.lock:
            for item in items:
                try:
                    self.queue.put_nowait(item)
                except Full:
                    # TODO: This is probably not what you want, but it will prevent OOM for now.
                    logger.warning(
                        f"Queue is full.  Dropping item.  Max queue size: {self.queue.maxsize}"
                    )

    def _get_next_batch(self) -> list[T]:
        batch: list[T] = []
        while len(batch) < self.max_batch_size:
            try:
                item = self.queue.get_nowait()
            except Empty:
                break
            else:
                batch.append(item)
        return batch

    def _process_batches(self) -> None:
        """Internal method that continuously processes batches of items from the queue."""
        while True:
            if current_batch := self._get_next_batch():
                try:
                    self.processor_fn(current_batch)
                except Exception as e:
                    if get_raise_on_captured_errors():
                        raise
                    logger.exception(f"Error processing batch: {e}")
                else:
                    for _ in current_batch:
                        self.queue.task_done()

            if self.stop_accepting_work_event.is_set() and self.queue.empty():
                break

            # Unless we are stopping, sleep for a the min_batch_interval
            if not self.stop_accepting_work_event.is_set():
                time.sleep(self.min_batch_interval)

    def stop_accepting_new_work_and_flush_queue(self) -> None:
        """Stops accepting new work and begins gracefully shutting down.

        Any new items enqueued after this call will not be processed!"""
        self.stop_accepting_work_event.set()
        self.processing_thread.join()

    def accept_new_work(self) -> None:
        """Resumes accepting new work."""
        self.stop_accepting_work_event.clear()
        # Start a new processing thread
        self.processing_thread = Thread(target=self._process_batches)
        self.processing_thread.daemon = True
        self.processing_thread.start()

    def is_accepting_new_work(self) -> bool:
        """Returns True if the processor is accepting new work."""
        return not self.stop_accepting_work_event.is_set()
