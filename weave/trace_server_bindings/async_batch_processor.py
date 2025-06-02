import atexit
import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from typing import Callable, Generic, TypeVar

import sentry_sdk

from weave.trace.context.tests_context import get_raise_on_captured_errors

T = TypeVar("T")
logger = logging.getLogger(__name__)

MAX_LOGFILES = 3
MAX_LOG_FILE_SIZE_BYTES = 1024 * 1024 * 512  # 512MB


class AsyncBatchProcessor(Generic[T]):
    """A class that asynchronously processes batches of items using a provided processor function."""

    def __init__(
        self,
        processor_fn: Callable[[list[T]], None],
        max_batch_size: int = 100,
        min_batch_interval: float = 1.0,
        max_queue_size: int = 10_000,
        max_retries_per_item: int = 5,
        enable_disk_fallback: bool = False,
        disk_fallback_path: str = ".weave_client_dropped_items_log.jsonl",
    ) -> None:
        """
        Initializes an instance of AsyncBatchProcessor.

        Args:
            processor_fn (Callable[[list[T]], None]): The function to process the batches of items.
            max_batch_size (int, optional): The maximum size of each batch. Defaults to 100.
            min_batch_interval (float, optional): The minimum interval between processing batches. Defaults to 1.0.
            max_queue_size (int, optional): The maximum number of items to hold in the queue. Defaults to 10_000.  0 means no limit.
            max_retries_per_item (int, optional): Maximum number of times to retry a failing item before dropping it. Defaults to 5.
            enable_disk_fallback (bool, optional): Whether to write dropped items to disk instead of discarding them. Defaults to False.
            disk_fallback_path (str, optional): Path to the JSON Lines file for dropped items.
        """
        self.processor_fn = processor_fn
        self.max_batch_size = max_batch_size
        self.min_batch_interval = min_batch_interval
        self.max_retries_per_item = max_retries_per_item
        self.enable_disk_fallback = enable_disk_fallback
        self.disk_fallback_path = Path(disk_fallback_path)
        self.queue: Queue[T] = Queue(maxsize=max_queue_size)
        self.lock = Lock()
        self.stop_accepting_work_event = Event()

        # Track failure counts for poison pill detection
        self.failure_counts: dict[int, int] = defaultdict(int)

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
                    item_id = id(item)
                    error_message = f"Queue is full. Dropping item. Item ID: {item_id}. Max queue size: {self.queue.maxsize}"
                    logger.warning(error_message)
                    sentry_sdk.capture_message(error_message, level="warning")
                    self._write_item_to_disk(item, error_message)

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
                    for item in current_batch:
                        self._mark_item_completed(item)
                except Exception as e:
                    if get_raise_on_captured_errors():
                        raise
                    logger.warning(
                        f"Batch processing failed, processing items individually. Error: {e}"
                    )
                    # Process each item individually to identify unprocessable items, this can be
                    # costly for large batches!
                    self._process_batch_individually(current_batch)

            if self.stop_accepting_work_event.is_set() and self.queue.empty():
                break

            # Unless we are stopping, sleep for a the min_batch_interval
            if not self.stop_accepting_work_event.is_set():
                time.sleep(self.min_batch_interval)

    def _mark_item_completed(self, item: T) -> None:
        """Mark an item as successfully completed - clear failure count and mark task done."""
        item_id = id(item)
        if item_id in self.failure_counts:
            del self.failure_counts[item_id]
        self.queue.task_done()

    def _handle_item_failure(self, item: T, error: Exception) -> bool:
        """
        Handle a failed item, tracking failures and deciding whether to retry or drop.

        Args:
            item: The failed item
            error: The exception that occurred

        Returns:
            bool: True if item should be dropped (unprocessable), False if it should be retried
        """
        item_id = id(item)
        self.failure_counts[item_id] += 1

        if self.failure_counts[item_id] >= self.max_retries_per_item:
            # Poison pill detected - log big error, write to disk, and drop the item
            error_message = (
                f"Unprocessable item detected: Item failed {self.failure_counts[item_id]} times "
                f"(max retries: {self.max_retries_per_item}). Dropping item permanently. "
                f"Item ID: {item_id}, Error: {error}"
            )
            logger.exception(error_message)
            sentry_sdk.capture_message(error_message, level="error")
            del self.failure_counts[item_id]
            self._write_item_to_disk(item, error_message)

            return True  # Drop the item!
        else:
            logger.warning(
                f"Item processing failed (attempt {self.failure_counts[item_id]}/{self.max_retries_per_item}). "
                f"Item ID: {item_id}, Error: {error}"
            )
            if get_raise_on_captured_errors():
                raise
            return False  # Retry the item

    def _requeue_or_drop_item(self, item: T) -> None:
        """Try to requeue a failed item, or drop it if queue is full."""
        try:
            self.queue.put_nowait(item)
        except Full:
            error_message = (
                f"Queue is full when trying to retry failed item. "
                f"Item ID: {id(item)} will be permanently dropped."
            )
            logger.exception(error_message)
            sentry_sdk.capture_message(error_message, level="error")

            self._write_item_to_disk(item, error_message)
            self.queue.task_done()

    def _process_batch_individually(self, batch: list[T]) -> None:
        """Process each item in a batch individually, handling failures appropriately."""
        for item in batch:
            if self._process_single_item(item):
                # Item succeeded or was dropped as poison pill
                self._mark_item_completed(item)
            else:
                # Item failed but should be retried
                self._requeue_or_drop_item(item)

    def _process_single_item(self, item: T) -> bool:
        """
        Process a single item and return True if successful, False if it should be retried.

        Args:
            item: The item to process

        Returns:
            bool: True if processing succeeded, False if it failed and should be retried
        """
        try:
            self.processor_fn([item])
        except Exception as e:
            return self._handle_item_failure(item, e)
        return True

    def _rotate_log_file_if_needed(self) -> None:
        """
        Rotate the log file if it exceeds the maximum size limit.

        This creates backup files with numbered suffixes (.1, .2, etc.) and removes
        old backups beyond the max_backup_files limit.
        """
        if not self.disk_fallback_path.exists():
            return

        try:
            file_size = self.disk_fallback_path.stat().st_size
            if file_size < MAX_LOG_FILE_SIZE_BYTES:
                return

            # Rotate existing backup files
            for i in range(MAX_LOGFILES - 1, 0, -1):
                old_backup = self.disk_fallback_path.with_suffix(f".{i}")
                new_backup = self.disk_fallback_path.with_suffix(f".{i + 1}")

                if old_backup.exists():
                    if i == MAX_LOGFILES - 1:
                        # Remove the oldest backup
                        old_backup.unlink()
                    else:
                        old_backup.rename(new_backup)

            # Move current log to .1
            backup_path = self.disk_fallback_path.with_suffix(".1")
            self.disk_fallback_path.rename(backup_path)
        except Exception as e:
            error_message = f"Failed to rotate log file {self.disk_fallback_path}: {e}"
            logger.exception(error_message)
            sentry_sdk.capture_message(error_message, level="error")

    def _write_item_to_disk(self, item: T, error_message: str) -> None:
        """
        Write a dropped item to disk in JSON Lines format.

        Args:
            item: The item to write to disk
            error_message: The reason why the item was dropped
        """
        if not self.enable_disk_fallback:
            return

        item_id = id(item)

        try:
            # Create the directory if it doesn't exist
            self.disk_fallback_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if rotation is needed before writing
            self._rotate_log_file_if_needed()

            # Prepare the record with metadata
            record = {
                "timestamp": time.time(),
                "error_message": error_message,
                "item_id": item_id,
                "item": item,
            }

            # Write to JSON Lines file
            with open(self.disk_fallback_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")

        except Exception as e:
            error_message = f"Failed to write dropped item {item_id} to disk: {e}"
            logger.exception(error_message)
            sentry_sdk.capture_message(error_message, level="error")
