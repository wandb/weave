import atexit
import logging
import time
from queue import Queue
from threading import Event, Lock, Thread
from typing import Callable, Generic, List, TypeVar

from weave.trace.context import get_raise_on_captured_errors
from weave.trace_server import requests

T = TypeVar("T")
logger = logging.getLogger(__name__)


class AsyncBatchProcessor(Generic[T]):
    """A class that asynchronously processes batches of items using a provided processor function."""

    def __init__(
        self,
        processor_fn: Callable[[List[T]], None],
        max_batch_size: int = 100,
        min_batch_interval: float = 1.0,
    ) -> None:
        """
        Initializes an instance of AsyncBatchProcessor.

        Args:
            processor_fn (Callable[[List[T]], None]): The function to process the batches of items.
            max_batch_size (int, optional): The maximum size of each batch. Defaults to 100.
            min_batch_interval (float, optional): The minimum interval between processing batches. Defaults to 1.0.
        """
        self.processor_fn = processor_fn
        self.max_batch_size = max_batch_size
        self.min_batch_interval = min_batch_interval
        self.queue: Queue[T] = Queue()
        self.lock = Lock()
        self.stop_event = Event()  # Use an event to signal stopping
        self.processing_thread = Thread(target=self._process_batches)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        atexit.register(self.wait_until_all_processed)  # Register cleanup function

    def enqueue(self, items: List[T]) -> None:
        """
        Enqueues a list of items to be processed.

        Args:
            items (List[T]): The items to be processed.
        """
        with self.lock:
            for item in items:
                self.queue.put(item)

    def _process_batches(self) -> None:
        """Internal method that continuously processes batches of items from the queue."""
        while True:
            current_batch: List[T] = []
            while not self.queue.empty() and len(current_batch) < self.max_batch_size:
                current_batch.append(self.queue.get())

            if current_batch:
                try:
                    self.processor_fn(current_batch)
                except requests.HTTPError as e:
                    if e.response.status_code == 413:
                        # 413: payload too large, don't raise just log
                        if get_raise_on_captured_errors():
                            raise
                        logger.error(f"Error processing batch: {e}")
                    else:
                        raise e

            if self.stop_event.is_set() and self.queue.empty():
                break

            # Unless we are stopping, sleep for a the min_batch_interval
            if not self.stop_event.is_set():
                time.sleep(self.min_batch_interval)

    def wait_until_all_processed(self) -> None:
        """Waits until all enqueued items have been processed."""
        self.stop_event.set()
        self.processing_thread.join()
