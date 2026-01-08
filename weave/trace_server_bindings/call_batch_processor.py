"""Batch processor optimized for call start/end pairing.

This module provides CallBatchProcessor, which maximizes the number of complete
calls sent to the server by pairing starts with ends at enqueue time rather than
relying on post-hoc consolidation within batches.
"""

import atexit
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread

from weave.telemetry.trace_sentry import SENTRY_AVAILABLE, sentry_sdk
from weave.trace.context.tests_context import get_raise_on_captured_errors
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.models import (
    CompleteBatchItem,
    EndBatchItem,
    StartBatchItem,
)

logger = logging.getLogger(__name__)

HEALTH_CHECK_INTERVAL = 5.0  # seconds
MAX_LOGFILES = 3
MAX_LOG_FILE_SIZE_BYTES = 1024 * 1024 * 512  # 512MB

# Type alias for batch items
BatchItem = StartBatchItem | EndBatchItem | CompleteBatchItem


def _start_thread(target: Callable[[], None], name: str | None = None) -> Thread:
    """Start a daemon thread and return it."""
    thread = Thread(target=target, daemon=True, name=name)
    thread.start()
    return thread


class CallBatchProcessor:
    """Batch processor that maximizes complete calls by pairing starts with ends at enqueue time.

    Unlike the generic AsyncBatchProcessor which uses pure FIFO batching, this processor:

    1. **Buffers starts**: Incoming StartBatchItems are held in a dict
    2. **Pairs on end arrival**: When an EndBatchItem arrives, it's immediately paired
       with its matching start (if buffered) to create a CompleteBatchItem
    3. **Timeout-based flush**: Starts that don't receive ends within `start_hold_timeout`
       are flushed to the ready queue as unpaired starts
    4. **Ready queue**: Only contains items ready to send - completes, flushed starts,
       and orphaned ends

    Batches contain maximum complete calls, reducing server-side merging and updates.

    Example flow:
        1. start_a arrives → buffered in pending_starts
        2. start_b arrives → buffered in pending_starts
        3. end_a arrives → paired with start_a → CompleteBatchItem queued
        4. timeout expires → start_b flushed as unpaired start
        5. batch sent: [complete_a, start_b]
    """

    def __init__(
        self,
        processor_fn: Callable[[list[BatchItem]], None],
        max_batch_size: int = 100,
        min_batch_interval: float = 1.0,
        max_queue_size: int = 10_000,
        start_hold_timeout: float = 10.0,
        enable_disk_fallback: bool = False,
        disk_fallback_path: str = ".weave_client_dropped_items_log.jsonl",
    ) -> None:
        """Initialize the CallBatchProcessor.

        Args:
            processor_fn: Function to process batches of items. Called with a list
                of BatchItems (starts, ends, or completes).
            max_batch_size: Maximum items per batch. Defaults to 100.
            min_batch_interval: Minimum seconds between batch processing. Defaults to 1.0.
            max_queue_size: Maximum ready queue size. Defaults to 10,000. Items are
                dropped when this limit is reached.
            start_hold_timeout: Seconds to hold starts waiting for their ends before
                flushing as unpaired. Defaults to 10.0. Should be >= call_start_delay
                in weave_client settings.
            enable_disk_fallback: If True, write dropped items to disk for later
                recovery. Defaults to False.
            disk_fallback_path: Path for the dropped items log file.
        """
        self.processor_fn = processor_fn
        self.max_batch_size = max_batch_size
        self.min_batch_interval = min_batch_interval
        self.start_hold_timeout = start_hold_timeout
        self.enable_disk_fallback = enable_disk_fallback
        self.disk_fallback_path = Path(disk_fallback_path)

        # Ready queue - items ready to be sent to server
        self.ready_queue: Queue[BatchItem] = Queue(maxsize=max_queue_size)

        # Pending starts - indexed by call_id for O(1) lookup
        # Maps call_id -> (StartBatchItem, enqueue_timestamp)
        self._pending_starts: dict[str, tuple[StartBatchItem, float]] = {}

        # Synchronization
        self._lock = Lock()
        self._stop_event = Event()
        self._dropped_item_count = 0

        # Worker threads
        self._processing_thread = _start_thread(
            self._process_batches_loop, "weave-call-batch-processor"
        )
        self._flush_thread = _start_thread(
            self._flush_stale_starts_loop, "weave-call-batch-flusher"
        )
        self._health_check_thread = _start_thread(
            self._health_check_loop, "weave-call-batch-health"
        )

        atexit.register(self.stop_accepting_new_work_and_flush_queue)

    # =========================================================================
    # Public API
    # =========================================================================

    @property
    def num_outstanding_jobs(self) -> int:
        """Returns count of items in ready queue plus pending starts."""
        with self._lock:
            return self.ready_queue.qsize() + len(self._pending_starts)

    def enqueue(self, items: list[BatchItem]) -> None:
        """Enqueue items, pairing starts with ends when possible.

        Args:
            items: List of batch items to enqueue.

        Behavior by item type:
            - StartBatchItem: Buffered in pending_starts, waiting for its end
            - EndBatchItem: If matching start exists, creates CompleteBatchItem.
                           Otherwise queues the orphaned end directly.
            - CompleteBatchItem: Queued directly (already paired)
        """
        now = time.time()

        with self._lock:
            for item in items:
                if isinstance(item, StartBatchItem):
                    self._handle_start(item, now)
                elif isinstance(item, EndBatchItem):
                    self._handle_end(item)
                elif isinstance(item, CompleteBatchItem):
                    self._queue_item(item)

    def stop_accepting_new_work_and_flush_queue(self) -> None:
        """Stop accepting new work and flush all pending items.

        This method:
        1. Flushes all pending starts to the ready queue
        2. Signals worker threads to stop
        3. Waits for processing to complete
        """
        # Flush all pending starts
        with self._lock:
            for call_id in list(self._pending_starts.keys()):
                item, _ = self._pending_starts.pop(call_id)
                self._queue_item(item)

        # Signal stop and wait for threads
        self._stop_event.set()
        self._processing_thread.join(timeout=30.0)
        self._flush_thread.join(timeout=5.0)
        self._health_check_thread.join(timeout=5.0)

    def accept_new_work(self) -> None:
        """Start accepting new work again after stopping."""
        self._stop_event.clear()

    def is_accepting_new_work(self) -> bool:
        """Returns True if the processor is accepting new work."""
        return not self._stop_event.is_set()

    # =========================================================================
    # Item Handling (called with lock held)
    # =========================================================================

    def _handle_start(self, item: StartBatchItem, timestamp: float) -> None:
        """Buffer a start item waiting for its end."""
        call_id = item.req.start.id
        if call_id is None or self.start_hold_timeout == 0:  # 0 means no buffering
            self._queue_item(item)
            return
        self._pending_starts[call_id] = (item, timestamp)

    def _handle_end(self, item: EndBatchItem) -> None:
        """Handle an end item - pair with buffered start if possible."""
        call_id = item.req.end.id
        if call_id is None:
            self._queue_item(item)
            return
        if call_id in self._pending_starts:
            start_item, _ = self._pending_starts.pop(call_id)
            self._queue_item(self._create_complete(start_item, item))
        else:
            self._queue_item(item)

    def _create_complete(
        self, start: StartBatchItem, end: EndBatchItem
    ) -> CompleteBatchItem:
        """Create a CompleteBatchItem by merging a start and end pair."""
        complete_call = tsi.CompletedCallSchemaForInsert(
            project_id=start.req.start.project_id,
            id=start.req.start.id,
            trace_id=start.req.start.trace_id,
            op_name=start.req.start.op_name,
            display_name=start.req.start.display_name,
            parent_id=start.req.start.parent_id,
            thread_id=start.req.start.thread_id,
            turn_id=start.req.start.turn_id,
            started_at=start.req.start.started_at,
            attributes=start.req.start.attributes,
            inputs=start.req.start.inputs,
            ended_at=end.req.end.ended_at,
            exception=end.req.end.exception,
            output=end.req.end.output,
            summary=end.req.end.summary,
            wb_user_id=start.req.start.wb_user_id,
            wb_run_id=start.req.start.wb_run_id,
            wb_run_step=start.req.start.wb_run_step,
            wb_run_step_end=end.req.end.wb_run_step_end,
        )
        return CompleteBatchItem(req=tsi.CallCompleteReq(complete=complete_call))

    def _queue_item(self, item: BatchItem) -> None:
        """Add an item to the ready queue.

        If the queue is full, the item is dropped (logged and optionally written to disk).
        """
        try:
            self.ready_queue.put_nowait(item)
        except Full:
            self._handle_dropped_item(item, "Ready queue full")

    # =========================================================================
    # Batch Processing
    # =========================================================================

    def _get_next_batch(self) -> list[BatchItem]:
        """Get the next batch of items from the ready queue.

        Returns up to max_batch_size items. Returns empty list if queue is empty.
        """
        batch: list[BatchItem] = []
        while len(batch) < self.max_batch_size:
            try:
                item = self.ready_queue.get_nowait()
                batch.append(item)
            except Empty:
                break
        return batch

    def _process_batches_loop(self) -> None:
        """Main processing loop - continuously processes batches from the ready queue."""
        while True:
            if batch := self._get_next_batch():
                try:
                    self.processor_fn(batch)
                except Exception as e:
                    if get_raise_on_captured_errors():
                        raise
                    logger.warning(
                        f"Batch processing failed, processing individually. Error: {e}"
                    )
                    self._process_batch_individually(batch)
                else:
                    # Mark all items as done
                    for _ in batch:
                        self.ready_queue.task_done()

            # Exit if stopping and queue is empty
            if self._stop_event.is_set() and self.ready_queue.empty():
                break

            # Sleep between batches unless stopping
            if not self._stop_event.is_set():
                time.sleep(self.min_batch_interval)

    def _process_batch_individually(self, batch: list[BatchItem]) -> None:
        """Process items one by one to identify and isolate poison pills."""
        for item in batch:
            try:
                self.processor_fn([item])
            except Exception as e:
                if get_raise_on_captured_errors():
                    raise
                self._handle_dropped_item(item, f"Processing failed: {e}")
            finally:
                self.ready_queue.task_done()

    # =========================================================================
    # Stale Start Flushing
    # =========================================================================

    def _flush_stale_starts_loop(self) -> None:
        """Background thread that periodically flushes stale starts."""
        while not self._stop_event.is_set():
            if self._stop_event.wait(timeout=1.0):
                break
            self._flush_stale_starts()

    def _flush_stale_starts(self) -> None:
        """Move starts older than start_hold_timeout to the ready queue."""
        if self.start_hold_timeout < 0:  # -1 means never flush, always wait for end
            return

        now = time.time()
        stale_items: list[StartBatchItem] = []

        with self._lock:
            stale_ids = [
                call_id
                for call_id, (_, timestamp) in self._pending_starts.items()
                if now - timestamp > self.start_hold_timeout
            ]
            for call_id in stale_ids:
                item, _ = self._pending_starts.pop(call_id)
                stale_items.append(item)

        for item in stale_items:
            try:
                self.ready_queue.put_nowait(item)
            except Full:
                self._handle_dropped_item(item, "Ready queue full during stale flush")

    # =========================================================================
    # Health Check
    # =========================================================================

    def _health_check_loop(self) -> None:
        """Monitor and revive worker threads if they die unexpectedly."""
        while not self._stop_event.is_set():
            if self._stop_event.wait(timeout=HEALTH_CHECK_INTERVAL):
                break

            if self._stop_event.is_set():
                break

            # Revive processing thread if dead
            if not self._processing_thread.is_alive():
                logger.warning("Processing thread died, reviving")
                try:
                    self._processing_thread = _start_thread(
                        self._process_batches_loop, "weave-call-batch-processor"
                    )
                    logger.info("Processing thread revived")
                except Exception as e:
                    logger.exception("Failed to revive processing thread")
                    if SENTRY_AVAILABLE:
                        sentry_sdk.capture_exception(e)

            # Revive flush thread if dead
            if not self._flush_thread.is_alive():
                logger.warning("Flush thread died, reviving")
                try:
                    self._flush_thread = _start_thread(
                        self._flush_stale_starts_loop, "weave-call-batch-flusher"
                    )
                    logger.info("Flush thread revived")
                except Exception as e:
                    logger.exception("Failed to revive flush thread")
                    if SENTRY_AVAILABLE:
                        sentry_sdk.capture_exception(e)

    # =========================================================================
    # Error Handling & Disk Fallback
    # =========================================================================

    def _handle_dropped_item(self, item: BatchItem, reason: str) -> None:
        """Handle a dropped item - log, report to Sentry, optionally write to disk."""
        self._dropped_item_count += 1
        item_id = self._get_item_id(item)
        error_message = (
            f"{reason}. Item ID: {item_id}. Total dropped: {self._dropped_item_count}"
        )

        # Log every 1000th drop to avoid log spam
        if self._dropped_item_count % 1000 == 1:
            logger.warning(error_message)
            if SENTRY_AVAILABLE:
                sentry_sdk.capture_message(
                    f"CallBatchProcessor dropped {self._dropped_item_count} items",
                    level="warning",
                )

        self._write_item_to_disk(item, error_message)

    def _get_item_id(self, item: BatchItem) -> str:
        """Get a unique identifier string for a batch item."""
        if isinstance(item, StartBatchItem):
            return f"{item.req.start.id}-start"
        elif isinstance(item, EndBatchItem):
            return f"{item.req.end.id}-end"
        elif isinstance(item, CompleteBatchItem):
            return f"{item.req.complete.id}-complete"
        return "unknown"

    def _write_item_to_disk(self, item: BatchItem, error_message: str) -> None:
        """Write a dropped item to disk in JSON Lines format for later recovery."""
        if not self.enable_disk_fallback:
            return

        try:
            self.disk_fallback_path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_log_file_if_needed()

            record = {
                "timestamp": time.time(),
                "error_message": error_message,
                "item_id": self._get_item_id(item),
                "item": item.model_dump() if hasattr(item, "model_dump") else str(item),
            }

            with open(self.disk_fallback_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception as e:
            logger.exception("Failed to write dropped item to disk")
            if SENTRY_AVAILABLE:
                sentry_sdk.capture_exception(e)

    def _rotate_log_file_if_needed(self) -> None:
        """Rotate the log file if it exceeds the maximum size limit."""
        if not self.disk_fallback_path.exists():
            return

        try:
            if self.disk_fallback_path.stat().st_size < MAX_LOG_FILE_SIZE_BYTES:
                return

            # Rotate existing backup files
            for i in range(MAX_LOGFILES - 1, 0, -1):
                old_backup = self.disk_fallback_path.with_suffix(f".{i}")
                new_backup = self.disk_fallback_path.with_suffix(f".{i + 1}")

                if old_backup.exists():
                    if i == MAX_LOGFILES - 1:
                        old_backup.unlink()
                    else:
                        old_backup.rename(new_backup)

            # Move current log to .1
            self.disk_fallback_path.rename(self.disk_fallback_path.with_suffix(".1"))
        except Exception as e:
            logger.exception("Failed to rotate log file")
            if SENTRY_AVAILABLE:
                sentry_sdk.capture_exception(e)
