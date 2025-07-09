import atexit
import json
import logging
import time
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from typing import Callable, Generic, TypeVar

import sentry_sdk

from weave.trace.context.tests_context import get_raise_on_captured_errors

T = TypeVar("T")
logger = logging.getLogger(__name__)

HEALTH_CHECK_INTERVAL = 5.0  # seconds
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
            enable_disk_fallback (bool, optional): Whether to write dropped items to disk instead of discarding them. Defaults to False.
            disk_fallback_path (str, optional): Path to the JSON Lines file for dropped items.
        """
        self.processor_fn = processor_fn
        self.max_batch_size = max_batch_size
        self.min_batch_interval = min_batch_interval
        self.enable_disk_fallback = enable_disk_fallback
        self.disk_fallback_path = Path(disk_fallback_path)
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
                    logger.warning(
                        f"Batch processing failed, processing items individually. Error: {e}"
                    )
                    # Process each item individually to identify unprocessable items, this can be
                    # costly for large batches!
                    self._process_batch_individually(current_batch)
                else:
                    for _ in current_batch:
                        self.queue.task_done()

            if self.stop_accepting_work_event.is_set() and self.queue.empty():
                break

            # Unless we are stopping, sleep for a the min_batch_interval
            if not self.stop_accepting_work_event.is_set():
                time.sleep(self.min_batch_interval)

    def _handle_item_failure(self, item: T, error: Exception) -> None:
        """
        Handle a failed item by treating it as a poison pill and dropping it.

        Args:
            item: The failed item
            error: The exception that occurred
        """
        item_id = id(item)
        error_message = (
            f"Unprocessable item detected, dropping item permanently. "
            f"Item ID: {item_id}, Error: {error}"
        )
        logger.exception(error_message)
        sentry_sdk.capture_message(error_message, level="error")
        self._write_item_to_disk(item, error_message)

    def _process_batch_individually(self, batch: list[T]) -> None:
        """Process each item in a batch individually, handling failures appropriately."""
        for item in batch:
            try:
                self.processor_fn([item])
            except Exception as e:
                if get_raise_on_captured_errors():
                    raise
                # Item failed - treat as poison pill and drop it
                self._handle_item_failure(item, e)
            finally:
                self.queue.task_done()

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
            # wait HEALTH_CHECK_INTERVAL unless we are shutting down
            if self.stop_accepting_work_event.wait(timeout=HEALTH_CHECK_INTERVAL):
                break

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
