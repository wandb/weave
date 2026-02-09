from __future__ import annotations

import datetime
import pathlib
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
    with pytest.raises(ValueError):
        processor.enqueue([end_item])

    with patch(
        "weave.trace_server_bindings.call_batch_processor.FLUSH_TIMEOUT_SECONDS",
        0.05,
    ):
        processor.stop_accepting_new_work_and_flush_queue()


def test_flush_drops_unpaired_items_and_clears_state() -> None:
    """Flush drops unpaired items and clears caches."""
    complete_fn = MagicMock()
    eager_fn = MagicMock()
    processor = CallBatchProcessor(complete_fn, eager_fn, min_batch_interval=0.01)

    processor.enqueue([_make_start_item("call-1", "trace-1")])
    processor.enqueue([_make_end_item("call-2")])

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
    eager_fn.assert_not_called()


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
