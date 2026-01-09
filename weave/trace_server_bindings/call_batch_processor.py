"""Batch processor optimized for call start/end pairing.

This module provides CallBatchProcessor, which extends AsyncBatchProcessor
to maximize complete calls by pairing starts with ends at enqueue time.
"""

import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.constants import EVALUATION_RUN_OP_NAME
from weave.trace_server_bindings.async_batch_processor import (
    AsyncBatchProcessor,
    start_thread,
)
from weave.trace_server_bindings.models import (
    CompleteBatchItem,
    EndBatchItem,
    StartBatchItem,
)

# Type alias for batch items
BatchItem = StartBatchItem | EndBatchItem | CompleteBatchItem

# Maximum delay (in seconds) for start_hold_timeout
MAX_CALL_START_DELAY = 600.0  # 10 minutes


class CallBatchProcessor(AsyncBatchProcessor[BatchItem]):
    """Batch processor that pairs starts with ends to maximize complete calls.

    Extends AsyncBatchProcessor with call-specific pairing behavior:

    1. **Buffers starts**: StartBatchItems are held in a dict
    2. **Pairs on end arrival**: EndBatchItems are paired with matching starts
       to create CompleteBatchItems
    3. **Timeout-based flush**: Starts without ends after `start_hold_timeout`
       are flushed as unpaired starts

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
            processor_fn: Function to process batches of items.
            max_batch_size: Maximum items per batch. Defaults to 100.
            min_batch_interval: Minimum seconds between processing. Defaults to 1.0.
            max_queue_size: Maximum queue size. Defaults to 10,000.
            start_hold_timeout: Seconds to hold starts waiting for ends.
                Use -1 for infinite wait, 0 for no buffering.
            enable_disk_fallback: Write dropped items to disk if True.
            disk_fallback_path: Path for dropped items log file.
        """
        super().__init__(
            processor_fn=processor_fn,
            max_batch_size=max_batch_size,
            min_batch_interval=min_batch_interval,
            max_queue_size=max_queue_size,
            enable_disk_fallback=enable_disk_fallback,
            disk_fallback_path=disk_fallback_path,
        )

        # Cap timeout: -1 means infinite, otherwise cap at MAX_CALL_START_DELAY
        if start_hold_timeout < 0:
            self.start_hold_timeout = start_hold_timeout
        else:
            self.start_hold_timeout = min(start_hold_timeout, MAX_CALL_START_DELAY)

        # Pending starts - indexed by call_id
        self._pending_starts: dict[str, tuple[StartBatchItem, float]] = {}
        # Start flush thread for stale starts
        self._flush_thread = start_thread(self._flush_stale_starts_loop)

    # =========================================================================
    # Overrides
    # =========================================================================

    @property
    def num_outstanding_jobs(self) -> int:
        """Returns count of items in queue plus pending starts."""
        with self.lock:
            return self.queue.qsize() + len(self._pending_starts)

    def enqueue(self, items: list[BatchItem]) -> None:
        """Enqueue items, pairing starts with ends when possible.

        Args:
            items: List of batch items to enqueue.

        Behavior by item type:
            - StartBatchItem: Buffered waiting for its end
            - EndBatchItem: Paired with matching start or queued as orphan
            - CompleteBatchItem: Queued directly (already paired)
        """
        now = time.time()

        with self.lock:
            for item in items:
                if isinstance(item, StartBatchItem):
                    self._handle_start(item, now)
                elif isinstance(item, EndBatchItem):
                    self._handle_end(item)
                elif isinstance(item, CompleteBatchItem):
                    self._queue_item(item)

    def stop_accepting_new_work_and_flush_queue(self) -> None:
        """Stop and flush all pending starts before shutdown."""
        # Flush all pending starts first
        with self.lock:
            for call_id in list(self._pending_starts.keys()):
                item, _ = self._pending_starts.pop(call_id)
                self._queue_item(item)

        # Signal stop
        self.stop_accepting_work_event.set()

        # Wait for threads (parent's threads + our flush thread)
        self.processing_thread.join(timeout=30.0)
        self._flush_thread.join(timeout=5.0)
        self.health_check_thread.join(timeout=5.0)

    # =========================================================================
    # Call-Specific Item Handling
    # =========================================================================

    def _handle_start(self, item: StartBatchItem, timestamp: float) -> None:
        """Buffer a start item waiting for its end."""
        call_id = item.req.start.id
        op_name = item.req.start.op_name or ""
        is_eval = EVALUATION_RUN_OP_NAME in op_name

        # Don't buffer: no ID, timeout=0, or evaluation ops
        if call_id is None or self.start_hold_timeout == 0 or is_eval:
            self._queue_item(item)
            return

        self._pending_starts[call_id] = (item, timestamp)

    def _handle_end(self, item: EndBatchItem) -> None:
        """Pair with buffered start if possible, otherwise queue as orphan."""
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
        """Create a CompleteBatchItem by merging start and end."""
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
        """Add item to queue, handling overflow via parent's disk fallback."""
        try:
            self.queue.put_nowait(item)
        except Exception:
            self._dropped_item_count += 1
            error_message = (
                f"Ready queue full. Dropping item. Max queue size: {self.queue.maxsize}"
            )

            # Only log the first dropped item and every 1000th thereafter
            if self._dropped_item_count % 1000 == 1:
                logger.warning(
                    f"{error_message}. Total dropped items: {self._dropped_item_count}"
                )

            self._write_item_to_disk(item, error_message)

    # =========================================================================
    # Stale Start Flushing
    # =========================================================================

    def _flush_stale_starts_loop(self) -> None:
        """Background thread that periodically flushes stale starts."""
        while not self.stop_accepting_work_event.is_set():
            if self.stop_accepting_work_event.wait(timeout=1.0):
                break
            self._flush_stale_starts()

    def _flush_stale_starts(self) -> None:
        """Move starts older than start_hold_timeout to the queue."""
        if self.start_hold_timeout < 0:  # -1 means never flush
            return

        now = time.time()
        stale_items: list[StartBatchItem] = []

        with self.lock:
            stale_ids = [
                call_id
                for call_id, (_, timestamp) in self._pending_starts.items()
                if now - timestamp > self.start_hold_timeout
            ]
            for call_id in stale_ids:
                item, _ = self._pending_starts.pop(call_id)
                stale_items.append(item)

        for item in stale_items:
            self._queue_item(item)
