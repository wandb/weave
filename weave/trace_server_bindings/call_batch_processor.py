"""Batch processor optimized for call start/end pairing.

This module provides CallBatchProcessor, which extends AsyncBatchProcessor
to maximize complete calls by pairing starts with ends at enqueue time.

Only complete calls (paired start + end) are ever sent to the server.
Unpaired starts/ends are held indefinitely until their counterpart arrives.
"""

import logging
from collections.abc import Callable

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
from weave.trace_server_bindings.models import (
    CompleteBatchItem,
    EndBatchItem,
    StartBatchItem,
)

logger = logging.getLogger(__name__)

BatchItem = StartBatchItem | EndBatchItem | CompleteBatchItem

# Default limit for pending (unpaired) calls
DEFAULT_MAX_PENDING_CALLS = 10_000


class CallBatchProcessor(AsyncBatchProcessor[BatchItem]):
    """Batch processor that pairs starts with ends to maximize complete calls.

    Only complete calls are ever sent. Starts and ends are held indefinitely
    until they can be paired. If the number of pending items exceeds the limit,
    an error is raised.
    """

    def __init__(
        self,
        processor_fn: Callable[[list[BatchItem]], None],
        max_batch_size: int = 100,
        min_batch_interval: float = 1.0,
        max_queue_size: int = 10_000,
        max_pending_calls: int = DEFAULT_MAX_PENDING_CALLS,
        enable_disk_fallback: bool = False,
        disk_fallback_path: str = ".weave_client_dropped_items_log.jsonl",
    ) -> None:
        """Initialize the CallBatchProcessor.

        Args:
            processor_fn: Function to process batches of complete items.
            max_batch_size: Maximum items per batch sent to processor_fn.
            min_batch_interval: Minimum seconds between processing.
            max_queue_size: Maximum queue size for ready-to-send items.
            max_pending_calls: Maximum pending unpaired calls before error.
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

        self.max_pending_calls = max_pending_calls
        self._pending_starts: dict[str, StartBatchItem] = {}
        self._pending_ends: dict[str, EndBatchItem] = {}

    @property
    def num_outstanding_jobs(self) -> int:
        """Return total number of items being processed or waiting."""
        with self.lock:
            return (
                self.queue.qsize() + len(self._pending_starts) + len(self._pending_ends)
            )

    @property
    def num_pending(self) -> int:
        """Return number of unpaired starts/ends waiting for their counterpart."""
        with self.lock:
            return len(self._pending_starts) + len(self._pending_ends)

    def enqueue(self, items: list[BatchItem]) -> None:
        """Enqueue items for processing.

        Starts and ends are paired immediately if possible. Only complete
        calls are queued for sending. Raises error if pending limit exceeded.
        """
        with self.lock:
            for item in items:
                if isinstance(item, StartBatchItem):
                    self._handle_start(item)
                elif isinstance(item, EndBatchItem):
                    self._handle_end(item)
                elif isinstance(item, CompleteBatchItem):
                    self._queue_item(item)

            # Check if we have too many pending items
            pending_count = len(self._pending_starts) + len(self._pending_ends)
            if pending_count > self.max_pending_calls:
                raise RuntimeError(
                    f"Too many pending calls ({pending_count}). "
                    f"Max allowed: {self.max_pending_calls}. "
                    "This may indicate calls are not being completed properly."
                )

    def stop_accepting_new_work_and_flush_queue(self) -> None:
        """Stop accepting work and flush the queue.

        Any unpaired starts/ends are logged and dropped - they cannot be sent
        as partial updates in this mode.
        """
        # Log any unpaired items before shutting down
        with self.lock:
            if self._pending_starts:
                logger.warning(
                    f"Shutting down with {len(self._pending_starts)} unpaired starts. "
                    "These calls will not be recorded."
                )
                for call_id, item in self._pending_starts.items():
                    self._write_item_to_disk(
                        item, f"Unpaired start dropped on shutdown: {call_id}"
                    )
                self._pending_starts.clear()

            if self._pending_ends:
                logger.warning(
                    f"Shutting down with {len(self._pending_ends)} unpaired ends. "
                    "These calls will not be recorded."
                )
                for call_id, item in self._pending_ends.items():
                    self._write_item_to_disk(
                        item, f"Unpaired end dropped on shutdown: {call_id}"
                    )
                self._pending_ends.clear()

        # Call parent implementation to flush the queue and stop threads
        super().stop_accepting_new_work_and_flush_queue()

    def _handle_start(self, item: StartBatchItem) -> None:
        """Handle a start item - pair with end if available, else hold."""
        call_id = item.req.start.id

        if call_id is None:
            # No ID means we can't pair it - this shouldn't happen but handle gracefully
            logger.warning("Received start without call_id, dropping")
            return

        # Check if we already have the end waiting
        if call_id in self._pending_ends:
            end_item = self._pending_ends.pop(call_id)
            self._queue_item(self._create_complete(item, end_item))
        else:
            # Hold the start until its end arrives
            self._pending_starts[call_id] = item

    def _handle_end(self, item: EndBatchItem) -> None:
        """Handle an end item - pair with start if available, else hold."""
        call_id = item.req.end.id

        if call_id is None:
            # No ID means we can't pair it - this shouldn't happen but handle gracefully
            logger.warning("Received end without call_id, dropping")
            return

        # Check if we already have the start waiting
        if call_id in self._pending_starts:
            start_item = self._pending_starts.pop(call_id)
            self._queue_item(self._create_complete(start_item, item))
        else:
            # Hold the end until its start arrives (handles race conditions)
            self._pending_ends[call_id] = item

    def _create_complete(
        self, start: StartBatchItem, end: EndBatchItem
    ) -> CompleteBatchItem:
        """Create a complete call from paired start and end."""
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
        return CompleteBatchItem(req=complete_call)

    def _queue_item(self, item: BatchItem) -> None:
        """Queue a complete item for sending."""
        try:
            self.queue.put_nowait(item)
        except Exception:
            self._dropped_item_count += 1
            error_message = (
                f"Ready queue full. Dropping item. Max queue size: {self.queue.maxsize}"
            )
            if self._dropped_item_count % 1000 == 1:
                logger.warning(
                    f"{error_message}. Total dropped items: {self._dropped_item_count}"
                )
            self._write_item_to_disk(item, error_message)
