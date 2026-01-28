"""Batch processor optimized for call start/end pairing.

This module provides CallBatchProcessor, which extends AsyncBatchProcessor
to maximize complete calls by pairing starts with ends at enqueue time.

Error Policy:
- Retryable batch-wide error on complete items → requeue items and raise SkipIndividualProcessingError
- Non-retryable error on complete items → log warning and drop items, continue with eager items
- Complete items depend on pairing so no item-by-item fallback is attempted
"""

import logging
import time
from collections.abc import Callable
from queue import Full

from cachetools import TTLCache

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.async_batch_processor import (
    AsyncBatchProcessor,
    SkipIndividualProcessingError,
    log_warning_with_sentry,
)
from weave.trace_server_bindings.models import (
    CompleteBatchItem,
    EndBatchItem,
    StartBatchItem,
)
from weave.utils.retry import _is_retryable_exception

logger = logging.getLogger(__name__)

BatchItem = StartBatchItem | EndBatchItem | CompleteBatchItem

# Default limit for pending (unpaired) calls
DEFAULT_MAX_PENDING_CALLS = 10_000
# Max batch size, this can be quite large, as long as traces are small
# Too-large batches are automatically split, and 413s are retried, lets
# err on the side of larger batch sizes for high velocity environments.
MAX_BATCH_SIZE = 1000
# TTL for eager call IDs (24 hours in seconds)
EAGER_CALL_ID_TTL_SECONDS = 24 * 60 * 60
# Timeout for flush: wait this long for in-flight calls to complete before dropping
FLUSH_TIMEOUT_SECONDS = 60


class CallBatchProcessor(AsyncBatchProcessor[BatchItem]):
    """Batch processor that pairs starts with ends to maximize complete calls.

    For normal ops: starts and ends are paired before sending as complete calls.
    For eager ops (marked with @op(eager_call_start=True)): starts are sent immediately
    via the legacy path, and ends are sent separately. This is useful for long-running
    operations like evaluations that should be visible in the UI immediately.
    """

    def __init__(
        self,
        complete_processor_fn: Callable[[list[CompleteBatchItem]], None],
        eager_processor_fn: Callable[[list[StartBatchItem | EndBatchItem]], None],
        max_batch_size: int = MAX_BATCH_SIZE,
        min_batch_interval: float = 1.0,
        max_queue_size: int = 10_000,
        max_pending_calls: int = DEFAULT_MAX_PENDING_CALLS,
        enable_disk_fallback: bool = False,
        disk_fallback_path: str = ".weave_client_dropped_items_log.jsonl",
    ) -> None:
        """Initialize the CallBatchProcessor.

        Args:
            complete_processor_fn: Function to process batches of complete items.
            eager_processor_fn: Function to process eager start/end items via v2 start/end endpoints.
            max_batch_size: Maximum items per batch sent to processor_fn.
            min_batch_interval: Minimum seconds between processing.
            max_queue_size: Maximum queue size for ready-to-send items.
            max_pending_calls: Maximum pending unpaired calls before error.
            enable_disk_fallback: Write dropped items to disk if True.
            disk_fallback_path: Path for dropped items log file.
        """
        # The parent class will use this for complete items
        super().__init__(
            processor_fn=self._process_mixed_batch,
            max_batch_size=max_batch_size,
            min_batch_interval=min_batch_interval,
            max_queue_size=max_queue_size,
            enable_disk_fallback=enable_disk_fallback,
            disk_fallback_path=disk_fallback_path,
        )

        self.complete_processor_fn = complete_processor_fn
        self.eager_processor_fn = eager_processor_fn
        self.max_pending_calls = max_pending_calls

        # Track pending starts/ends waiting for their counterpart
        self._pending_starts: dict[str, StartBatchItem] = {}
        self._pending_ends: dict[str, EndBatchItem] = {}

        # Track which calls were sent as eager (start sent immediately)
        # Uses TTL cache to auto-expire entries to prevent unbounded growth
        self._eager_call_ids: TTLCache[str, bool] = TTLCache(
            maxsize=max_pending_calls, ttl=EAGER_CALL_ID_TTL_SECONDS
        )

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

        Note: For start items, prefer using enqueue_start() which supports
        the eager_call_start flag for ops that need immediate visibility.
        """
        with self.lock:
            for item in items:
                if isinstance(item, StartBatchItem):
                    self._handle_start(item, eager_call_start=False)
                elif isinstance(item, EndBatchItem):
                    self._handle_end(item)
                elif isinstance(item, CompleteBatchItem):
                    # Already complete, queue directly
                    self._queue_item(item)

            self._check_pending_limit()

    def enqueue_start(
        self, item: StartBatchItem, *, eager_call_start: bool = False
    ) -> None:
        """Enqueue a start item with eager_call_start flag.

        Args:
            item: The start batch item to enqueue.
            eager_call_start: If True, send start immediately rather than batching.
                This is set from the op's eager_call_start property at definition time.
                Useful for long-running ops that should be visible in the UI immediately.
        """
        with self.lock:
            self._handle_start(item, eager_call_start=eager_call_start)
            self._check_pending_limit()

    def _check_pending_limit(self) -> None:
        """Check if we have too many pending items and raise if so."""
        pending_count = len(self._pending_starts) + len(self._pending_ends)
        if pending_count > self.max_pending_calls:
            raise RuntimeError(
                f"Too many pending calls ({pending_count}). "
                f"Max allowed: {self.max_pending_calls}. "
                "This may indicate calls are not being completed properly."
            )

    def stop_accepting_new_work_and_flush_queue(self) -> None:
        """Stop accepting work and flush the queue.

        Waits up to FLUSH_TIMEOUT_SECONDS for in-flight calls to complete
        (starts to pair with their ends) and for the queue to drain. This
        supports the common pattern of calling client.finish() at the end
        of execution when operations may still be completing (example: large
        payloads are still serializing, but user proc has completed).

        Drops unpaired starts and ends after the timeout expires.
        """
        # Wait for pending items to pair (in-flight calls completing)
        # Don't set stop event yet - processing thread needs to keep running
        # and ends need to be able to come in and pair with pending starts
        # Break early if all calls are matched (done)
        deadline = time.monotonic() + FLUSH_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            with self.lock:
                pending_count = len(self._pending_starts) + len(self._pending_ends)
            if pending_count == 0:
                break
            time.sleep(0.1)

        # Shutdown, processing thread will drain queue then exit
        self.stop_accepting_work_event.set()

        # Drop any remaining unpaired items with warnings
        with self.lock:
            if self._pending_starts:
                logger.warning(
                    f"Flush timeout: dropping {len(self._pending_starts)} calls "
                    f"that did not complete within {FLUSH_TIMEOUT_SECONDS}s."
                )
                for call_id, start_item in self._pending_starts.items():
                    self._write_item_to_disk(
                        start_item,
                        f"Unpaired start dropped after flush timeout: {call_id}",
                    )
                self._pending_starts.clear()

            if self._pending_ends:
                logger.warning(
                    f"Flush timeout: dropping {len(self._pending_ends)} orphaned "
                    f"call ends that did not pair within {FLUSH_TIMEOUT_SECONDS}s."
                )
                for call_id, end_item in self._pending_ends.items():
                    self._write_item_to_disk(
                        end_item, f"Unpaired end dropped after flush timeout: {call_id}"
                    )
                self._pending_ends.clear()

            self._eager_call_ids.clear()

        # The processing thread will process all remaining queue items before
        # exiting; this may take longer than the timeout if the queue is large,
        # but we don't drop queue items if they've already been paired.
        self.processing_thread.join()
        self.health_check_thread.join()

    def _handle_start(
        self, item: StartBatchItem, *, eager_call_start: bool = False
    ) -> None:
        """Handle a start item - pair with end if available, else hold or send eager.

        Args:
            item: The start batch item.
            eager_call_start: If True, send start immediately rather than batching.
                Defined at op definition time via @op(eager_call_start=True).
        """
        call_id = item.req.start.id

        if call_id is None:
            logger.warning("Received start without call_id, dropping")
            return

        if eager_call_start:
            self._eager_call_ids[call_id] = True
            self._queue_item(item)
            # If end already arrived (race condition), queue it separately too
            if call_id in self._pending_ends:
                end_item = self._pending_ends.pop(call_id)
                self._queue_item(end_item)  # Queue as EndBatchItem, not complete
            return

        # Check if we already have the end waiting
        if call_id in self._pending_ends:
            end_item = self._pending_ends.pop(call_id)
            complete_item = self._create_complete(item, end_item)
            self._queue_item(complete_item)
        else:
            # Hold the start until its end arrives
            self._pending_starts[call_id] = item

    def _handle_end(self, item: EndBatchItem) -> None:
        """Handle an end item - pair with start if available, else hold."""
        call_id = item.req.end.id
        if call_id is None:
            logger.warning("Received end without call_id, dropping")
            return

        # Check if start was already sent
        if call_id in self._eager_call_ids:
            self._eager_call_ids.pop(call_id, None)
            self._queue_item(item)  # Send end via eager path
            return

        # Check if we already have the start waiting
        if call_id in self._pending_starts:
            start_item = self._pending_starts.pop(call_id)
            complete_item = self._create_complete(start_item, item)
            self._queue_item(complete_item)
        else:
            # Hold the end until its start arrives (handles race conditions)
            self._pending_ends[call_id] = item

    def _create_complete(
        self, start: StartBatchItem, end: EndBatchItem
    ) -> CompleteBatchItem:
        """Create a complete call from paired start and end.

        Args:
            start: The start batch item containing call start information.
            end: The end batch item containing call end information.

        Returns:
            A CompleteBatchItem combining start and end data.

        Raises:
            ValueError: If start item is missing required id or trace_id.
        """
        if start.req.start.id is None:
            raise ValueError("Cannot create complete call: start item missing id")
        if start.req.start.trace_id is None:
            raise ValueError("Cannot create complete call: start item missing trace_id")

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
            otel_dump=start.req.start.otel_dump,
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
        """Queue an item for sending."""
        try:
            self.queue.put_nowait(item)
        except Full:
            self._dropped_item_count += 1
            item_id = id(item)
            error_message = (
                f"Queue is full. Dropping item. Item ID: {item_id}. "
                f"Max queue size: {self.queue.maxsize}."
                f"Total dropped items: {self._dropped_item_count}."
            )
            # Only log and report to Sentry on first drop and every 1000th thereafter
            if self._dropped_item_count % 1000 == 1:
                log_warning_with_sentry(error_message)
            self._write_item_to_disk(item, error_message)

    def _process_mixed_batch(self, batch: list[BatchItem]) -> None:
        """Process a mixed batch by splitting into complete and eager items.

        Error Policy:
        - Retryable error on complete items → requeue and raise SkipIndividualProcessingError
        - Non-retryable error on complete items → log warning, drop items, continue with eager
        - Complete items depend on pairing, so no item-by-item fallback is attempted
        """
        complete_items: list[CompleteBatchItem] = []
        eager_items: list[StartBatchItem | EndBatchItem] = []

        for item in batch:
            if isinstance(item, CompleteBatchItem):
                complete_items.append(item)
            elif isinstance(item, (StartBatchItem, EndBatchItem)):
                eager_items.append(item)

        complete_error: Exception | None = None

        # Process complete items via the v2 complete endpoint
        if complete_items:
            try:
                self.complete_processor_fn(complete_items)
            except Exception as e:
                complete_error = e
                if _is_retryable_exception(e):
                    # Requeue all complete items for later retry
                    for item in complete_items:
                        self._queue_item(item)
                    # Skip eager processing only if there are no eager items
                    if not eager_items:
                        raise SkipIndividualProcessingError(
                            "Complete batch failed with retryable error, items requeued"
                        ) from e
                else:
                    # Non-retryable: log warning and drop complete items
                    ids = [item.req.id for item in complete_items]
                    log_warning_with_sentry(
                        f"Dropping {len(complete_items)} complete calls due to non-retryable error: {e}. "
                        f"Call IDs: {ids}"
                    )

        # Process eager items via the v2 start/end endpoints (always attempt if present)
        if eager_items:
            self.eager_processor_fn(eager_items)

        # If complete items failed with retryable error but we had eager items, raise after processing eager
        if complete_error is not None and _is_retryable_exception(complete_error):
            raise SkipIndividualProcessingError(
                "Complete batch failed with retryable error, items requeued"
            ) from complete_error
