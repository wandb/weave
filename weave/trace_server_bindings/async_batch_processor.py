import atexit
import logging
import time
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from typing import Callable, Generic, TypeVar

import sentry_sdk

from weave.trace.context.tests_context import get_raise_on_captured_errors

T = TypeVar("T")
logger = logging.getLogger(__name__)

HEALTH_CHECK_INTERVAL = 5.0  # seconds


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

        # Processing Thread
        self.processing_thread = start_thread(self._process_batches)
        # Health check thread, to revive the processing thread if it dies
        self.health_check_thread = start_thread(self._health_check)

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
                    # Check if the health check has died, restart it if so
                    self._ensure_health_check_alive()

                    # TODO: This is probably not what you want, but it will prevent OOM for now.
                    error = f"Queue is full.  Dropping item.  Max queue size: {self.queue.maxsize}"
                    logger.warning(error)
                    sentry_sdk.capture_message(error)

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
        self.health_check_thread.join()

    def accept_new_work(self) -> None:
        """Resumes accepting new work."""
        self.stop_accepting_work_event.clear()
        # Start a new processing thread
        self.processing_thread = start_thread(self._process_batches)
        # Restart health check thread
        self.health_check_thread = start_thread(self._health_check)

    def is_accepting_new_work(self) -> bool:
        """Returns True if the processor is accepting new work."""
        return not self.stop_accepting_work_event.is_set()

    def _ensure_health_check_alive(self) -> None:
        """Ensures the health check thread is alive, restarts if needed."""
        if not self.health_check_thread.is_alive() and self.is_accepting_new_work():
            logger.warning("Health check thread died, attempting to revive it")
            try:
                self.health_check_thread = start_thread(self._health_check)
                logger.info("Health check thread successfully revived")
            except Exception as e:
                logger.exception(f"Failed to revive health check thread: {e}")
                sentry_sdk.capture_exception(e)

    def _health_check(self) -> None:
        """Health check thread that monitors and revives the processing thread if it dies."""
        while self.is_accepting_new_work():
            time.sleep(HEALTH_CHECK_INTERVAL)

            # If we're shutting down, don't revive
            if self.stop_accepting_work_event.is_set():
                break

            # Check if processing thread is dead
            if not self.processing_thread.is_alive():
                logger.warning("Processing thread died, attempting to revive it")
                try:
                    # Create and start a new processing thread
                    self.processing_thread = start_thread(self._process_batches)
                    logger.info("Processing thread successfully revived")
                except Exception as e:
                    logger.exception(f"Failed to revive processing thread: {e}")
                    sentry_sdk.capture_exception(e)


def start_thread(target: Callable[[], None]) -> Thread:
    """Starts a thread and returns it."""
    thread = Thread(target=target)
    thread.daemon = True
    thread.start()
    return thread
