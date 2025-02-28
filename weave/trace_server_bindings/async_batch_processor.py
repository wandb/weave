from __future__ import annotations

import atexit
import logging
import time
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Callable, Generic, TypeVar

from weave.trace.context.tests_context import get_raise_on_captured_errors

T = TypeVar("T")
logger = logging.getLogger(__name__)


@dataclass
class RetryTracker(Generic[T]):
    item: T
    retry_count: int = 0


class AsyncBatchProcessor(Generic[T]):
    """A class that asynchronously processes batches of items using a provided processor function."""

    def __init__(
        self,
        processor_fn: Callable[[list[T]], None],
        max_batch_size: int = 100,
        min_batch_interval: float = 1.0,
        max_retries: int = 3,
        process_timeout: float = 30.0,
    ) -> None:
        """
        Initializes an instance of AsyncBatchProcessor.

        Args:
            processor_fn (Callable[[list[T]], None]): The function to process the batches of items.
            max_batch_size (int, optional): The maximum size of each batch. Defaults to 100.
            min_batch_interval (float, optional): The minimum interval between processing batches. Defaults to 1.0.
            max_retries (int, optional): Maximum number of retry attempts for a batch when thread dies. Defaults to 3.
            process_timeout (float, optional): Maximum time in seconds to wait for a batch to process before moving on.
                                              Defaults to 30.0. Set to 0 to disable timeout.
        """
        self.processor_fn = processor_fn
        self.max_batch_size = max_batch_size
        self.min_batch_interval = min_batch_interval
        self.max_retries = max_retries
        self.process_timeout = process_timeout
        self.queue: Queue[RetryTracker[T]] = Queue()
        self.lock = Lock()
        self.stop_event = Event()

        # Tracks in-progress batch for recovery after thread death
        self.current_batch: list[RetryTracker[T]] = []
        self.processing_thread = self._create_processing_thread()
        atexit.register(self.wait_until_all_processed)  # Ensures clean shutdown

    def _create_processing_thread(self) -> Thread:
        thread = Thread(target=self._process_batches)
        thread.daemon = True
        thread.start()
        return thread

    def _ensure_processing_thread_alive(self) -> None:
        """Ensures processing thread is alive, restarting it if necessary.

        Thread death detection and recovery strategy:
        1. Quick check without lock for performance
        2. Re-check with lock for thread safety
        3. Re-enqueue failed batch at the back of the queue (to avoid rapid successive failures)
        4. Create a new thread outside the lock to avoid deadlocks
        """
        if self.processing_thread.is_alive() or self.stop_event.is_set():
            return

        with self.lock:
            # Re-check after acquiring the lock
            if self.processing_thread.is_alive() or self.stop_event.is_set():
                return

            logger.info("Processing thread died, restarting...")

            # Case 1: Nothing to retry, just reset retry counter
            if not self.current_batch:
                pass  # No need to reset anything as retry counts are per item

            # Case 2: Retry the batch by putting items into the back of the queue
            else:
                for tracker in self.current_batch:
                    if tracker.retry_count < self.max_retries:
                        logger.info(
                            f"Retrying item (attempt {tracker.retry_count + 1}/{self.max_retries})"
                        )
                        # Increment retry count before re-enqueueing
                        tracker.retry_count += 1
                        self.queue.put(tracker)
                    else:
                        logger.warning(
                            f"Item exceeded max retries ({self.max_retries}), dropping item"
                        )
                self.current_batch = []

        # Create thread outside lock to prevent deadlocks
        self.processing_thread = self._create_processing_thread()

    def enqueue(self, items: list[T]) -> None:
        """Enqueues a list of items to be processed."""
        if not items:
            return

        self._ensure_processing_thread_alive()
        with self.lock:
            for item in items:
                tracker = RetryTracker(item=item)
                self.queue.put(tracker)

    def _process_batches(self) -> None:
        """Main thread loop that processes batches from the queue.

        Thread safety approach:
        1. Collect batch items outside lock when possible
        2. Update shared state (current_batch) under lock
        3. Process batch outside lock to avoid blocking other operations
        4. Only clear batch tracking on success
        5. Implement timeout mechanism to prevent indefinite blocking
        """
        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                # Safely collect a batch of items from the queue
                current_batch: list[RetryTracker[T]] = _safely_get_batch(
                    self.queue, self.max_batch_size
                )
                if not current_batch:
                    continue

                # Keep track of the current batch in case of thread death
                with self.lock:
                    self.current_batch = current_batch

                # Extract the actual items from the trackers for processing
                items_to_process = [tracker.item for tracker in current_batch]

                processed = False  # Flag to track if batch was processed

                if self.process_timeout > 0:
                    # If a timeout is set, use a separate thread to enforce the timeout.
                    # This is necessary because the processing function may block indefinitely.
                    processing_completed = Event()
                    processing_error = None

                    def process_with_timeout() -> None:
                        nonlocal processing_error

                        try:
                            self.processor_fn(items_to_process)
                        except Exception as e:
                            processing_error = e
                            processing_completed.set()
                        else:
                            processing_completed.set()

                    # Start and wait for processing to complete or timeout
                    processing_thread = Thread(target=process_with_timeout)
                    processing_thread.daemon = True
                    processing_thread.start()
                    processing_success = processing_completed.wait(self.process_timeout)

                    # Case 1: Processing timed out
                    if not processing_success:
                        logger.info(
                            f"Processing batch of {len(current_batch)} items timed out after {self.process_timeout}s. "
                            f"Moving to next batch. Items will be retried if retry attempts remain."
                        )
                        # Queue items back up for retry if they haven't exceeded max retries
                        with self.lock:
                            for tracker in current_batch:
                                if tracker.retry_count < self.max_retries:
                                    tracker.retry_count += 1
                                    self.queue.put(tracker)
                                else:
                                    logger.error(
                                        f"Item processing timed out and exceeded max retries ({self.max_retries}). "
                                        f"Dropping item."
                                    )
                            self.current_batch = []

                    # Case 2: Processing completed with an error
                    elif processing_error is not None:
                        with self.lock:
                            self.current_batch = []
                        if get_raise_on_captured_errors():
                            raise processing_error
                        logger.exception(f"Error processing batch: {processing_error}")

                    # Case 3: Processing completed successfully
                    else:
                        with self.lock:
                            self.current_batch = []

                    processed = True  # Mark as processed regardless of outcome

                # Only process if not already processed with timeout mechanism.
                if not processed:
                    try:
                        self.processor_fn(items_to_process)
                    except Exception as e:
                        # Clear the current batch even on error to avoid retrying indefinitely
                        with self.lock:
                            self.current_batch = []
                        if get_raise_on_captured_errors():
                            raise
                        logger.exception(f"Error processing batch: {e}")
                    else:
                        # If we succeed, then clear it out ahead of the next one
                        with self.lock:
                            self.current_batch = []

                # Rate limiting to prevent CPU overuse on empty/small queues
                if not self.stop_event.is_set():
                    time.sleep(self.min_batch_interval)
            except Exception as e:
                # SystemExit, KeyboardInterrupt, etc. will still kill the thread
                logger.exception(f"Unexpected error in processing thread: {e}")
                break  # Thread death will trigger recovery on next operation

    def wait_until_all_processed(self) -> None:
        """Waits for all enqueued items to be processed with timeout protection.

        Shutdown sequence:
        1. Signal thread to stop accepting new work
        2. Wait for in-progress work to complete with timeout
        3. Check and restart thread if needed for recovery
        4. Warn if processing timed out with pending items
        """
        self.stop_event.set()

        max_wait_time = 10.0  # Hard timeout to prevent indefinite hanging
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            with self.lock:
                if self.queue.empty() and not self.current_batch:
                    break

            # Thread recovery check during shutdown
            if not self.processing_thread.is_alive():
                self._ensure_processing_thread_alive()

            time.sleep(0.1)

        with self.lock:
            if not self.queue.empty() or self.current_batch:
                logger.warning(
                    f"Timed out waiting for processing to complete. "
                    f"Queue size: {self.queue.qsize()}, Current batch size: {len(self.current_batch)}"
                )

        if self.processing_thread.is_alive():
            self.processing_thread.join(timeout=1.0)


def _safely_get_batch(queue: Queue[T], max_batch_size: int) -> list[T]:
    batch: list[T] = []
    for _ in range(max_batch_size):
        try:
            item = queue.get(block=False)
            batch.append(item)
        except Empty:
            break
    return batch
