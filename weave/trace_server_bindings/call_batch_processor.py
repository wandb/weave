"""Batch processor optimized for call start/end pairing.

This module provides CallBatchProcessor, which extends AsyncBatchProcessor
to maximize complete calls by pairing starts with ends at enqueue time.

Handles the race condition where ends may arrive before their starts in
concurrent execution by buffering both starts and ends until they can be paired.
"""

import logging
import time
from collections.abc import Callable

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

logger = logging.getLogger(__name__)

BatchItem = StartBatchItem | EndBatchItem | CompleteBatchItem

MAX_CALL_START_DELAY = 600.0  # 10 minutes
FLUSH_POLL_INTERVAL = 0.1  # 100ms


class CallBatchProcessor(AsyncBatchProcessor[BatchItem]):
    """Batch processor that pairs starts with ends to maximize complete calls.

    Buffers both starts and ends to handle race conditions in concurrent execution
    where ends may arrive before their corresponding starts.
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
            max_batch_size: Maximum items per batch.
            min_batch_interval: Minimum seconds between processing.
            max_queue_size: Maximum queue size.
            start_hold_timeout: Seconds to hold items waiting for pairing.
                Use -1 for infinite wait (capped at MAX_CALL_START_DELAY during flush),
                0 for no buffering.
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

        if start_hold_timeout < 0:
            self.start_hold_timeout = start_hold_timeout
        else:
            self.start_hold_timeout = min(start_hold_timeout, MAX_CALL_START_DELAY)

        self._pending_starts: dict[str, tuple[StartBatchItem, float]] = {}
        self._pending_ends: dict[str, tuple[EndBatchItem, float]] = {}
        self._is_flushing = False
        self._flush_thread = start_thread(self._flush_stale_items_loop)

    @property
    def num_outstanding_jobs(self) -> int:
        with self.lock:
            return (
                self.queue.qsize() + len(self._pending_starts) + len(self._pending_ends)
            )

    def enqueue(self, items: list[BatchItem]) -> None:
        now = time.time()
        with self.lock:
            for item in items:
                if isinstance(item, StartBatchItem):
                    self._handle_start(item, now)
                elif isinstance(item, EndBatchItem):
                    self._handle_end(item, now)
                elif isinstance(item, CompleteBatchItem):
                    self._queue_item(item)

    def stop_accepting_new_work_and_flush_queue(
        self, flush_timeout: float | None = None
    ) -> None:
        if flush_timeout is None:
            flush_timeout = MAX_CALL_START_DELAY

        if self.start_hold_timeout == 0:
            actual_wait = 0.0
        elif self.start_hold_timeout > 0:
            actual_wait = min(self.start_hold_timeout, flush_timeout)
        else:
            actual_wait = flush_timeout

        self._is_flushing = True

        if actual_wait > 0:
            deadline = time.time() + actual_wait
            while time.time() < deadline:
                with self.lock:
                    if not self._pending_starts and not self._pending_ends:
                        break
                time.sleep(FLUSH_POLL_INTERVAL)

        with self.lock:
            for call_id in list(self._pending_starts.keys()):
                item, _ = self._pending_starts.pop(call_id)
                self._queue_item(item)
            for call_id in list(self._pending_ends.keys()):
                item, _ = self._pending_ends.pop(call_id)
                self._queue_item(item)

        self.stop_accepting_work_event.set()
        self.processing_thread.join(timeout=30.0)
        self._flush_thread.join(timeout=5.0)
        self.health_check_thread.join(timeout=5.0)

    def accept_new_work(self) -> None:
        self._is_flushing = False
        super().accept_new_work()
        self._flush_thread = start_thread(self._flush_stale_items_loop)

    def _handle_start(self, item: StartBatchItem, timestamp: float) -> None:
        call_id = item.req.start.id
        op_name = item.req.start.op_name or ""
        is_eval = EVALUATION_RUN_OP_NAME in op_name

        if (
            call_id is None
            or self.start_hold_timeout == 0
            or is_eval
            or self._is_flushing
        ):
            self._queue_item(item)
            return

        if call_id in self._pending_ends:
            end_item, _ = self._pending_ends.pop(call_id)
            self._queue_item(self._create_complete(item, end_item))
            return

        self._pending_starts[call_id] = (item, timestamp)

    def _handle_end(self, item: EndBatchItem, timestamp: float) -> None:
        call_id = item.req.end.id

        if call_id is None:
            self._queue_item(item)
            return

        if call_id in self._pending_starts:
            start_item, _ = self._pending_starts.pop(call_id)
            self._queue_item(self._create_complete(start_item, item))
        elif self.start_hold_timeout != 0 and not self._is_flushing:
            self._pending_ends[call_id] = (item, timestamp)
        else:
            self._queue_item(item)

    def _create_complete(
        self, start: StartBatchItem, end: EndBatchItem
    ) -> CompleteBatchItem:
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

    def _flush_stale_items_loop(self) -> None:
        while not self.stop_accepting_work_event.is_set():
            if self.stop_accepting_work_event.wait(timeout=1.0):
                break
            self._flush_stale_items()

    def _flush_stale_items(self) -> None:
        if self.start_hold_timeout < 0:
            return

        now = time.time()
        stale_starts: list[StartBatchItem] = []
        stale_ends: list[EndBatchItem] = []

        with self.lock:
            for call_id, (item, timestamp) in list(self._pending_starts.items()):
                if now - timestamp > self.start_hold_timeout:
                    self._pending_starts.pop(call_id)
                    stale_starts.append(item)

            for call_id, (item, timestamp) in list(self._pending_ends.items()):
                if now - timestamp > self.start_hold_timeout:
                    self._pending_ends.pop(call_id)
                    stale_ends.append(item)

        for item in stale_starts:
            self._queue_item(item)
        for item in stale_ends:
            self._queue_item(item)
