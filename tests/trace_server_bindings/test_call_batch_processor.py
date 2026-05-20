from __future__ import annotations

import datetime
import pathlib
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.call_batch_processor import CallBatchProcessor
from weave.trace_server_bindings.models import (
    CompleteBatchItem,
    EndBatchItem,
    StartBatchItem,
)


def _make_start_item(
    call_id: str, trace_id: str, *, project_id: str = "proj"
) -> StartBatchItem:
    """Create a start batch item for a call.

    Args:
        call_id: Call identifier to use.
        trace_id: Trace identifier to use.
        project_id: Project identifier to use.

    Returns:
        StartBatchItem: A start item for use in tests.

    Examples:
        >>> item = _make_start_item("call-1", "trace-1")
        >>> item.req.start.id
        'call-1'
    """
    started_at = datetime.datetime.now(datetime.timezone.utc)
    start = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id,
        trace_id=trace_id,
        op_name="op",
        started_at=started_at,
        attributes={},
        inputs={},
    )
    return StartBatchItem(req=tsi.CallStartReq(start=start))


def _make_end_item(call_id: str, *, project_id: str = "proj") -> EndBatchItem:
    """Create an end batch item for a call.

    Args:
        call_id: Call identifier to use.
        project_id: Project identifier to use.

    Returns:
        EndBatchItem: An end item for use in tests.

    Examples:
        >>> item = _make_end_item("call-1")
        >>> item.req.end.id
        'call-1'
    """
    ended_at = datetime.datetime.now(datetime.timezone.utc)
    end = tsi.EndedCallSchemaForInsert(
        project_id=project_id,
        id=call_id,
        ended_at=ended_at,
        summary={},
    )
    return EndBatchItem(req=tsi.CallEndReq(end=end))


def _make_complete_item(
    call_id: str, trace_id: str, *, project_id: str = "proj"
) -> CompleteBatchItem:
    """Create a complete batch item for a call.

    Args:
        call_id: Call identifier to use.
        trace_id: Trace identifier to use.
        project_id: Project identifier to use.

    Returns:
        CompleteBatchItem: A complete item for use in tests.

    Examples:
        >>> item = _make_complete_item("call-1", "trace-1")
        >>> item.req.id
        'call-1'
    """
    started_at = datetime.datetime.now(datetime.timezone.utc)
    ended_at = started_at + datetime.timedelta(seconds=1)
    complete = tsi.CompletedCallSchemaForInsert(
        project_id=project_id,
        id=call_id,
        trace_id=trace_id,
        op_name="op",
        started_at=started_at,
        ended_at=ended_at,
        attributes={},
        inputs={},
        summary={},
    )
    return CompleteBatchItem(req=complete)


@pytest.mark.parametrize("start_first", [True, False])
def test_start_end_pairing_orders(start_first: bool) -> None:
    """Start/end pairing works regardless of arrival order."""
    complete_fn = MagicMock()
    eager_fn = MagicMock()
    processor = CallBatchProcessor(complete_fn, eager_fn, min_batch_interval=0.01)

    start = _make_start_item("call-1", "trace-1")
    end = _make_end_item("call-1")

    if start_first:
        processor.enqueue([start])
        processor.enqueue([end])
    else:
        processor.enqueue([end])
        processor.enqueue([start])
    processor.stop_accepting_new_work_and_flush_queue()

    complete_fn.assert_called_once()
    batch = complete_fn.call_args[0][0]
    assert len(batch) == 1
    assert isinstance(batch[0], CompleteBatchItem)
    assert batch[0].req.id == "call-1"
    eager_fn.assert_not_called()


def test_eager_start_and_end_use_eager_processor() -> None:
    """Eager starts and their ends should use the eager processor."""
    complete_fn = MagicMock()
    eager_fn = MagicMock()
    processor = CallBatchProcessor(complete_fn, eager_fn, min_batch_interval=0.01)

    start = _make_start_item("call-1", "trace-1")
    end = _make_end_item("call-1")
    processor.enqueue_start(start, eager_call_start=True)
    processor.enqueue([end])
    processor.stop_accepting_new_work_and_flush_queue()

    complete_fn.assert_not_called()
    eager_fn.assert_called_once()
    eager_items = eager_fn.call_args[0][0]
    assert {type(item) for item in eager_items} == {StartBatchItem, EndBatchItem}


def test_complete_item_routes_to_complete_processor() -> None:
    """Complete items bypass pairing and go directly to the complete processor."""
    complete_fn = MagicMock()
    eager_fn = MagicMock()
    processor = CallBatchProcessor(complete_fn, eager_fn, min_batch_interval=0.01)

    processor.enqueue([_make_complete_item("call-1", "trace-1")])
    processor.stop_accepting_new_work_and_flush_queue()

    complete_fn.assert_called_once()
    batch = complete_fn.call_args[0][0]
    assert len(batch) == 1
    assert isinstance(batch[0], CompleteBatchItem)
    eager_fn.assert_not_called()


def test_pending_limit_raises_runtime_error() -> None:
    """Exceeding max_pending_calls raises an error."""
    processor = CallBatchProcessor(
        MagicMock(),
        MagicMock(),
        max_pending_calls=1,
        min_batch_interval=0.01,
    )

    processor.enqueue([_make_start_item("call-1", "trace-1")])
    with pytest.raises(RuntimeError):
        processor.enqueue([_make_start_item("call-2", "trace-2")])

    with patch(
        "weave.trace_server_bindings.call_batch_processor.FLUSH_TIMEOUT_SECONDS",
        0.05,
    ):
        processor.stop_accepting_new_work_and_flush_queue()


def test_missing_trace_id_raises_value_error() -> None:
    """Missing trace_id raises when pairing into a complete call."""
    complete_fn = MagicMock()
    eager_fn = MagicMock()
    processor = CallBatchProcessor(complete_fn, eager_fn, min_batch_interval=0.01)

    started_at = datetime.datetime.now(datetime.timezone.utc)
    start = tsi.StartedCallSchemaForInsert(
        project_id="proj",
        id="call-1",
        trace_id=None,
        op_name="op",
        started_at=started_at,
        attributes={},
        inputs={},
    )
    start_item = StartBatchItem(req=tsi.CallStartReq(start=start))
    end_item = _make_end_item("call-1")

    processor.enqueue([start_item])
    with pytest.raises(ValueError, match="missing trace_id"):
        processor.enqueue([end_item])

    with patch(
        "weave.trace_server_bindings.call_batch_processor.FLUSH_TIMEOUT_SECONDS",
        0.05,
    ):
        processor.stop_accepting_new_work_and_flush_queue()


def test_drain_queue_skips_pending_pair_wait() -> None:
    """User flush drains the send queue without waiting on pending pairs.

    Pins WB-34557. Under `WEAVE_USE_CALLS_COMPLETE=true`, the old
    `stop_accepting_new_work_and_flush_queue` path made `client.flush()`
    hang up to FLUSH_TIMEOUT_SECONDS waiting for in-flight starts to pair.
    The drain path used by `WeaveClient.flush()` must:
      1. return quickly even when pending pairs exist,
      2. leave _pending_starts / _pending_ends / _eager_call_ids untouched
         so the bulk-endpoint pairing optimization survives the flush,
      3. NOT orphan-send pending items (those still belong to in-flight calls).
    """
    complete_fn = MagicMock()
    eager_fn = MagicMock()
    processor = CallBatchProcessor(complete_fn, eager_fn, min_batch_interval=0.01)

    # Simulate an in-flight non-eager call: start enqueued, end not yet.
    pending_start = _make_start_item("call-1", "trace-1")
    processor.enqueue([pending_start])
    # And an in-flight eager call: start sent immediately, end not yet.
    eager_start = _make_start_item("call-2", "trace-2")
    processor.enqueue_start(eager_start, eager_call_start=True)

    t0 = time.monotonic()
    processor.drain_queue(timeout=5.0)
    elapsed = time.monotonic() - t0

    # Drain must return quickly — well under any pairing budget.
    assert elapsed < 2.0, f"drain_queue blocked for {elapsed:.2f}s"

    # Pending state preserved so pairing can still happen later.
    assert "call-1" in processor._pending_starts
    assert "call-2" in processor._eager_call_ids
    # Neither processor was called with the still-in-flight non-eager start.
    complete_fn.assert_not_called()
    # The eager start was queued and sent immediately by enqueue_start;
    # the eager processor may have already drained it. Either way, we did
    # not orphan-send "call-1".
    sent_items = [item for call in eager_fn.call_args_list for item in call.args[0]]
    assert pending_start not in sent_items

    # Processor is still accepting work.
    assert processor.is_accepting_new_work()

    # Cleanup
    with patch(
        "weave.trace_server_bindings.call_batch_processor.FLUSH_TIMEOUT_SECONDS",
        0.05,
    ):
        processor.stop_accepting_new_work_and_flush_queue()


def test_drain_queue_processes_already_paired_items() -> None:
    """Drain still sends what's already paired and queued."""
    complete_fn = MagicMock()
    eager_fn = MagicMock()
    processor = CallBatchProcessor(complete_fn, eager_fn, min_batch_interval=0.01)

    # Pair up a call so it lands in the send queue.
    processor.enqueue([_make_start_item("call-1", "trace-1")])
    processor.enqueue([_make_end_item("call-1")])

    processor.drain_queue(timeout=5.0)

    complete_fn.assert_called_once()
    batch = complete_fn.call_args[0][0]
    assert len(batch) == 1
    assert batch[0].req.id == "call-1"

    # Cleanup
    with patch(
        "weave.trace_server_bindings.call_batch_processor.FLUSH_TIMEOUT_SECONDS",
        0.05,
    ):
        processor.stop_accepting_new_work_and_flush_queue()


def test_flush_eager_sends_unpaired_items_and_clears_state() -> None:
    """Flush sends unpaired items via the eager v2 endpoints and clears caches."""
    complete_fn = MagicMock()
    eager_fn = MagicMock()
    processor = CallBatchProcessor(complete_fn, eager_fn, min_batch_interval=0.01)

    orphan_start = _make_start_item("call-1", "trace-1")
    orphan_end = _make_end_item("call-2")
    processor.enqueue([orphan_start])
    processor.enqueue([orphan_end])

    with patch(
        "weave.trace_server_bindings.call_batch_processor.FLUSH_TIMEOUT_SECONDS",
        0.05,
    ):
        processor.stop_accepting_new_work_and_flush_queue()

    assert processor.num_pending == 0
    assert processor._pending_starts == {}
    assert processor._pending_ends == {}
    assert len(processor._eager_call_ids) == 0
    complete_fn.assert_not_called()
    # Both orphans should have been handed to the eager processor (possibly
    # across one or multiple batched invocations).
    sent_items = [item for call in eager_fn.call_args_list for item in call.args[0]]
    assert orphan_start in sent_items
    assert orphan_end in sent_items


def test_queue_full_writes_to_disk(tmp_path: pathlib.Path) -> None:
    """Queue full behavior writes dropped items to disk."""
    log_path = tmp_path / "call_batch_dropped.jsonl"
    processor = CallBatchProcessor(
        MagicMock(),
        MagicMock(),
        max_queue_size=1,
        min_batch_interval=0.5,
        enable_disk_fallback=True,
        disk_fallback_path=str(log_path),
    )

    processor.stop_accepting_new_work_and_flush_queue()

    processor.queue.put_nowait(_make_start_item("call-1", "trace-1"))
    processor._queue_item(_make_start_item("call-2", "trace-2"))

    assert log_path.exists()
    assert "Queue is full" in log_path.read_text()


def test_retryable_error_requeues_complete_batch() -> None:
    """Retryable error on complete_processor_fn requeues items and raises SkipIndividualProcessingError."""
    from weave.trace_server_bindings.async_batch_processor import (
        SkipIndividualProcessingError,
    )

    complete_fn = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "503",
            request=httpx.Request("POST", "http://example.com"),
            response=httpx.Response(
                503, request=httpx.Request("POST", "http://example.com")
            ),
        )
    )
    eager_fn = MagicMock()
    processor = CallBatchProcessor(complete_fn, eager_fn, min_batch_interval=0.01)

    # Stop background processing to test _process_mixed_batch in isolation
    processor.stop_accepting_work_event.set()
    processor.processing_thread.join(timeout=1)
    processor.health_check_thread.join(timeout=1)

    complete_items = [
        _make_complete_item("call-1", "trace-1"),
        _make_complete_item("call-2", "trace-2"),
    ]

    # Call _process_mixed_batch directly to test error handling
    with pytest.raises(SkipIndividualProcessingError):
        processor._process_mixed_batch(complete_items)

    # Items should be requeued
    assert processor.queue.qsize() == 2
    eager_fn.assert_not_called()


@pytest.mark.disable_logging_error_check
def test_non_retryable_error_drops_complete_items_but_eager_succeeds(caplog) -> None:
    """Non-retryable error drops complete items but eager items still process."""
    import logging

    complete_fn = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "400 Bad Request",
            request=httpx.Request("POST", "http://example.com"),
            response=httpx.Response(
                400, request=httpx.Request("POST", "http://example.com")
            ),
        )
    )
    eager_fn = MagicMock()
    processor = CallBatchProcessor(complete_fn, eager_fn, min_batch_interval=0.01)

    # Stop background processing to test _process_mixed_batch in isolation
    processor.stop_accepting_work_event.set()
    processor.processing_thread.join(timeout=1)
    processor.health_check_thread.join(timeout=1)

    complete_items = [_make_complete_item("call-1", "trace-1")]
    eager_items = [_make_start_item("call-2", "trace-2")]

    # Capture logs from weave.telemetry.trace_sentry (where log_warning_with_sentry logs)
    caplog.set_level(logging.WARNING, logger="weave.telemetry.trace_sentry")

    # Should not raise - logs warning and continues
    processor._process_mixed_batch(complete_items + eager_items)

    # Complete items not requeued (dropped)
    assert processor.queue.qsize() == 0
    # Eager items were still processed
    eager_fn.assert_called_once()
    assert len(eager_fn.call_args[0][0]) == 1
    # Warning was logged
    assert any("Dropping" in record.message for record in caplog.records)


def test_mixed_batch_error_does_not_break_eager_processing() -> None:
    """Complete path failure does not prevent eager items from being processed."""
    from weave.trace_server_bindings.async_batch_processor import (
        SkipIndividualProcessingError,
    )

    complete_fn = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "503",
            request=httpx.Request("POST", "http://example.com"),
            response=httpx.Response(
                503, request=httpx.Request("POST", "http://example.com")
            ),
        )
    )
    eager_fn = MagicMock()
    processor = CallBatchProcessor(complete_fn, eager_fn, min_batch_interval=0.01)

    # Stop background processing to test _process_mixed_batch in isolation
    processor.stop_accepting_work_event.set()
    processor.processing_thread.join(timeout=1)
    processor.health_check_thread.join(timeout=1)

    complete_items = [_make_complete_item("call-1", "trace-1")]
    eager_items = [_make_start_item("call-2", "trace-2")]

    # Should raise SkipIndividualProcessingError after processing eager items
    with pytest.raises(SkipIndividualProcessingError):
        processor._process_mixed_batch(complete_items + eager_items)

    # Complete items should be requeued
    assert processor.queue.qsize() == 1
    # Eager items were still processed despite complete error
    eager_fn.assert_called_once()
    assert len(eager_fn.call_args[0][0]) == 1
