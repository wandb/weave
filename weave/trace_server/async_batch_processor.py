import atexit
import logging
import time
from queue import Empty, Queue
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
        self.queue: Queue[T] = Queue()
        self.lock = Lock()
        self.stop_event = Event()

        # Tracks in-progress batch for recovery after thread death
        self.current_batch: list[T] = []
        self.current_batch_retries = 0  # Tracks retry attempts for the current batch
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
                self.current_batch_retries = 0

            # Case 2: Retry the batch by putting items into the back of the queue
            elif self.current_batch_retries < self.max_retries:
                logger.info(
                    f"Retrying batch of {len(self.current_batch)} items "
                    f"(attempt {self.current_batch_retries + 1}/{self.max_retries})"
                )
                for item in self.current_batch:
                    self.queue.put(item)
                self.current_batch_retries += 1

            # Case 3: Max retries exceeded, drop the batch
            else:
                logger.warning(
                    f"Batch of {len(self.current_batch)} items exceeded max retries "
                    f"({self.max_retries}), dropping batch"
                )
                self.current_batch = []
                self.current_batch_retries = 0

        # Create thread outside lock to prevent deadlocks
        self.processing_thread = self._create_processing_thread()

    def enqueue(self, items: list[T]) -> None:
        """Enqueues a list of items to be processed."""
        if not items:
            return

        # Ensure the thread is alive before queuing to ensure items will actually be processed
        self._ensure_processing_thread_alive()

        with self.lock:
            for item in items:
                self.queue.put(item)

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
                current_batch: list[T] = []
                for _ in range(self.max_batch_size):
                    try:
                        item = self.queue.get(block=False)
                        current_batch.append(item)
                    except Empty:
                        break

                if not current_batch:
                    continue

                # Keep track of the current batch in case of thread death
                with self.lock:
                    self.current_batch = current_batch

                if self.process_timeout > 0:
                    # Use a separate thread with timeout for processing to avoid blocking
                    processing_completed = Event()
                    processing_error = [None]

                    def process_with_timeout():
                        try:
                            self.processor_fn(current_batch)
                        except (SystemExit, KeyboardInterrupt) as e:
                            raise
                        except Exception as e:
                            processing_error[0] = e
                            processing_completed.set()
                        else:
                            processing_completed.set()

                    processing_thread = Thread(target=process_with_timeout)
                    processing_thread.daemon = True
                    processing_thread.start()

                    # Wait for processing to complete or timeout
                    processing_success = processing_completed.wait(
                        timeout=self.process_timeout
                    )

                    if not processing_success:
                        # Processing timed out
                        logger.warning(
                            f"Processing batch of {len(current_batch)} items timed out after {self.process_timeout}s. "
                            f"Moving to next batch. This batch will be retried if retry attempts remain."
                        )
                        # Re-enqueue the batch for retry if attempts remain
                        with self.lock:
                            if self.current_batch_retries < self.max_retries:
                                logger.info(
                                    f"Re-enqueueing timed out batch (attempt {self.current_batch_retries + 1}/{self.max_retries})"
                                )
                                for item in current_batch:
                                    self.queue.put(item)
                                self.current_batch_retries += 1
                            else:
                                logger.error(
                                    f"Batch processing timed out and exceeded max retries ({self.max_retries}). "
                                    f"Dropping {len(current_batch)} items."
                                )
                                self.current_batch_retries = 0
                            self.current_batch = []
                    elif processing_error[0] is not None:
                        # Processing completed with an error
                        if get_raise_on_captured_errors():
                            raise processing_error[0]
                        logger.exception(
                            f"Error processing batch: {processing_error[0]}"
                        )
                        with self.lock:
                            self.current_batch = []
                            self.current_batch_retries = 0
                    else:
                        # Processing completed successfully
                        with self.lock:
                            self.current_batch = []
                            self.current_batch_retries = 0
                else:
                    # Process without timeout (original behavior)
                    try:
                        self.processor_fn(current_batch)
                    except Exception as e:
                        if get_raise_on_captured_errors():
                            raise
                        logger.exception(f"Error processing batch: {e}")
                    else:
                        # If we succeed, then clear it out ahead of the next one
                        with self.lock:
                            self.current_batch = []
                            self.current_batch_retries = 0

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
