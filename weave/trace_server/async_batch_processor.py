import atexit
import logging
import time
from queue import Queue
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
        max_retries: int = 3,
    ) -> None:
        """
        Initializes an instance of AsyncBatchProcessor.

        Args:
            processor_fn (Callable[[list[T]], None]): The function to process the batches of items.
            max_batch_size (int, optional): The maximum size of each batch. Defaults to 100.
            min_batch_interval (float, optional): The minimum interval between processing batches. Defaults to 1.0.
            max_retries (int, optional): Maximum number of retry attempts for a batch when thread dies. Defaults to 3.
        """
        self.processor_fn = processor_fn
        self.max_batch_size = max_batch_size
        self.min_batch_interval = min_batch_interval
        self.max_retries = max_retries
        self.queue: Queue[T] = Queue()
        self.lock = Lock()
        self.stop_event = Event()  # Use an event to signal stopping
        self.current_batch: list[T] = []  # Track the current batch being processed
        self.current_batch_retries = 0  # Track retry attempts for the current batch
        self.processing_thread = self._create_processing_thread()
        atexit.register(self.wait_until_all_processed)  # Register cleanup function

    def _create_processing_thread(self) -> Thread:
        """Creates and starts a new processing thread.

        Returns:
            Thread: The newly created and started processing thread.
        """
        thread = Thread(target=self._process_batches)
        thread.daemon = True
        thread.start()
        return thread

    def _ensure_processing_thread_alive(self) -> None:
        """Ensures that the processing thread is alive, restarting it if necessary.

        If the thread has died, any batch that was being processed will be retried
        up to the maximum number of retry attempts.
        """
        # First check if thread is alive without acquiring the lock
        if self.processing_thread.is_alive() or self.stop_event.is_set():
            return

        with self.lock:
            # Double-check after acquiring the lock
            if not self.processing_thread.is_alive() and not self.stop_event.is_set():
                logger.warning("Processing thread died, restarting...")

                # If there was a batch being processed when the thread died, retry it
                if self.current_batch and self.current_batch_retries < self.max_retries:
                    logger.info(
                        f"Retrying batch of {len(self.current_batch)} items "
                        f"(attempt {self.current_batch_retries + 1}/{self.max_retries})"
                    )
                    # Re-enqueue the items at the front of the queue
                    temp_queue = Queue()
                    for item in self.current_batch:
                        temp_queue.put(item)

                    # Add the rest of the items from the original queue
                    while not self.queue.empty():
                        temp_queue.put(self.queue.get())

                    # Replace the queue with our new queue that has the failed batch at the front
                    self.queue = temp_queue
                    self.current_batch_retries += 1
                elif self.current_batch:
                    logger.warning(
                        f"Batch of {len(self.current_batch)} items exceeded max retries "
                        f"({self.max_retries}), dropping batch"
                    )
                    # Reset the current batch since we're giving up on retrying
                    self.current_batch = []
                    self.current_batch_retries = 0

                # Release the lock before creating a new thread to avoid deadlock
                # Store a local reference to avoid race conditions
                current_batch = self.current_batch.copy() if self.current_batch else []

        # Create a new processing thread outside the lock
        self.processing_thread = self._create_processing_thread()

    def enqueue(self, items: list[T]) -> None:
        """
        Enqueues a list of items to be processed.

        Args:
            items (list[T]): The items to be processed.
        """
        if not items:
            return

        # Ensure the processing thread is alive before enqueueing items
        self._ensure_processing_thread_alive()

        with self.lock:
            for item in items:
                self.queue.put(item)

    def _process_batches(self) -> None:
        """Internal method that continuously processes batches of items from the queue."""
        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                # Collect items for the current batch
                current_batch: list[T] = []
                while (
                    not self.queue.empty() and len(current_batch) < self.max_batch_size
                ):
                    current_batch.append(self.queue.get())

                if current_batch:
                    # Update the current batch tracking with the lock
                    # But release it before calling the processor function
                    with self.lock:
                        self.current_batch = current_batch.copy()

                    # Process the batch outside the lock
                    success = False
                    try:
                        self.processor_fn(current_batch)
                        success = True
                    except Exception as e:
                        if get_raise_on_captured_errors():
                            raise
                        logger.exception(f"Error processing batch: {e}")
                        # Keep current_batch set so it can be retried if thread dies

                    # Only update state if successful
                    if success:
                        with self.lock:
                            self.current_batch = []
                            self.current_batch_retries = 0

                # Unless we are stopping, sleep for the min_batch_interval
                if not self.stop_event.is_set():
                    time.sleep(self.min_batch_interval)
            except Exception as e:
                # Log any unexpected exceptions in the thread loop itself
                # This won't catch SystemExit, KeyboardInterrupt, etc. which will kill the thread
                logger.exception(f"Unexpected error in processing thread: {e}")
                # Exit the thread loop on unexpected errors
                break

    def wait_until_all_processed(self) -> None:
        """Waits until all enqueued items have been processed."""
        self.stop_event.set()

        # Keep checking and restarting the thread until the queue is empty
        # and there's no current batch being processed
        max_wait_time = 10.0  # Maximum time to wait in seconds
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            # Check if we're done
            with self.lock:
                if self.queue.empty() and not self.current_batch:
                    break

            # Ensure the processing thread is alive
            if not self.processing_thread.is_alive():
                self._ensure_processing_thread_alive()

            # Give a little time for processing to continue
            time.sleep(0.1)

        # If we still have items after the timeout, log a warning
        with self.lock:
            if not self.queue.empty() or self.current_batch:
                logger.warning(
                    f"Timed out waiting for processing to complete. "
                    f"Queue size: {self.queue.qsize()}, Current batch size: {len(self.current_batch)}"
                )

        # Try to join the thread if it's alive
        if self.processing_thread.is_alive():
            self.processing_thread.join(timeout=1.0)
