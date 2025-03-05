from __future__ import annotations

import atexit
import logging
import time
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from typing import Callable, Generic, TypeVar, cast

from pydantic import BaseModel

from weave.trace.context.tests_context import get_raise_on_captured_errors
from weave.trace_server_bindings.sqlite_wal import SQLiteWriteAheadLog

T = TypeVar("T")
PydanticT = TypeVar("PydanticT", bound=BaseModel)
logger = logging.getLogger(__name__)


class AsyncBatchProcessor(Generic[T]):
    """A class that asynchronously processes batches of items using a provided processor function.

    Can optionally use a SQLite write-ahead log (WAL) for durability.
    """

    def __init__(
        self,
        processor_fn: Callable[[list[T]], None],
        max_batch_size: int = 100,
        min_batch_interval: float = 1.0,
        max_queue_size: int = 10_000,
        use_wal: bool = False,
        wal_path: str | None = None,
    ) -> None:
        """
        Initializes an instance of AsyncBatchProcessor.

        Args:
            processor_fn (Callable[[list[T]], None]): The function to process the batches of items.
            max_batch_size (int, optional): The maximum size of each batch. Defaults to 100.
            min_batch_interval (float, optional): The minimum interval between processing batches. Defaults to 1.0.
            max_queue_size (int, optional): The maximum number of items to hold in the queue. Defaults to 10_000. 0 means no limit.
            use_wal (bool, optional): Whether to use a SQLite write-ahead log for durability. Defaults to False.
            wal_path (str, optional): Path to the SQLite WAL database. If None, a default path will be used.
        """
        self.processor_fn = processor_fn
        self.max_batch_size = max_batch_size
        self.min_batch_interval = min_batch_interval
        self.queue: Queue[T] = Queue(maxsize=max_queue_size)
        self.lock = Lock()
        self.stop_accepting_work_event = Event()

        # WAL support
        self.use_wal = use_wal
        self.wal = None
        if self.use_wal:
            # Initialize the WAL
            self.wal = SQLiteWriteAheadLog(db_path=wal_path)
            # Recover any items from the WAL
            self._recover_from_wal()

        # Start the processing thread
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

    def _recover_from_wal(self) -> None:
        """Recover items from the WAL and add them to the queue.

        This method is only used when use_wal is True.
        """
        if not self.use_wal or self.wal is None:
            return

        try:
            items = self.wal.get_all_items()
            if not items:
                return

            logger.info(f"Recovering {len(items)} items from WAL")

            # Group items by type
            recovered_items = []
            wal_ids_to_delete = []

            for item in items:
                wal_id = item["data"].pop("_wal_id", None)
                if wal_id is not None:
                    wal_ids_to_delete.append(wal_id)

                # This is a simplified recovery that assumes the items can be
                # directly reconstructed from the WAL data.
                # In a real implementation, you would need to handle the specific
                # item types and their reconstruction.
                try:
                    # Try to import the class dynamically
                    item_type = item["type"]
                    module_parts = item_type.split(".")
                    if len(module_parts) == 1:
                        # If no module specified, assume it's from the current module
                        # This is a simplification and might not work for all cases
                        from weave.trace_server_bindings.remote_http_trace_server import (
                            EndBatchItem,
                            StartBatchItem,
                        )

                        if item_type == "StartBatchItem":
                            from weave.trace_server import trace_server_interface as tsi

                            req = tsi.CallStartReq.model_validate(item["data"]["req"])
                            recovered_items.append(StartBatchItem(req=req))
                        elif item_type == "EndBatchItem":
                            from weave.trace_server import trace_server_interface as tsi

                            req = tsi.CallEndReq.model_validate(item["data"]["req"])
                            recovered_items.append(EndBatchItem(req=req))
                except Exception as e:
                    logger.exception(f"Error recovering item from WAL: {e}")

            # Add recovered items to the queue
            for item in recovered_items:
                try:
                    self.queue.put_nowait(cast(T, item))
                except Full:
                    logger.warning(
                        f"Queue is full during recovery. Dropping item. Max queue size: {self.queue.maxsize}"
                    )

            # Delete processed items from the WAL
            self.wal.delete_items(wal_ids_to_delete)

            logger.info(f"Recovered {len(recovered_items)} items from WAL")
        except Exception as e:
            logger.exception(f"Error recovering from WAL: {e}")

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
        if not items:
            return

        # If using WAL, write to the WAL first for durability
        if (
            self.use_wal
            and self.wal is not None
            and all(isinstance(item, BaseModel) for item in items)
        ):
            try:
                # Cast to list[BaseModel] since we've verified all items are BaseModel instances
                self.wal.append(cast(list[BaseModel], items))
            except Exception as e:
                logger.exception(f"Error writing to WAL: {e}")
                # Continue anyway to try to process the items

        # Then add to the in-memory queue
        with self.lock:
            for item in items:
                try:
                    self.queue.put_nowait(item)
                except Full:
                    logger.warning(
                        f"Queue is full. Dropping item. Max queue size: {self.queue.maxsize}"
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
                    # Process the batch
                    self.processor_fn(current_batch)

                    # If using WAL, clear the WAL after successful processing
                    if self.use_wal and self.wal is not None:
                        try:
                            self.wal.clear()
                        except Exception as e:
                            logger.exception(f"Error clearing WAL: {e}")
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
