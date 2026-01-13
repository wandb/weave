"""Tests for CallBatchProcessor.

Tests the call-specific pairing behavior that extends AsyncBatchProcessor.
The simplified CallBatchProcessor:
- Always holds starts/ends until they can be paired
- Only sends complete calls (paired start + end)
- Raises error if pending calls exceed limit
- On shutdown, unpaired items are dropped (logged to disk)
"""

from __future__ import annotations

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.call_batch_processor import (
    DEFAULT_MAX_PENDING_CALLS,
    CallBatchProcessor,
)
from weave.trace_server_bindings.models import (
    CompleteBatchItem,
    EndBatchItem,
    StartBatchItem,
)


def make_start(
    call_id: str, project_id: str = "entity/project", op_name: str = "test_op"
) -> StartBatchItem:
    """Helper to create a StartBatchItem for testing."""
    return StartBatchItem(
        req=tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=f"trace_{call_id}",
                op_name=op_name,
                started_at="2024-01-01T00:00:00Z",
                inputs={},
                attributes={},
            )
        )
    )


def make_end(call_id: str, project_id: str = "entity/project") -> EndBatchItem:
    """Helper to create an EndBatchItem for testing."""
    return EndBatchItem(
        req=tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                ended_at="2024-01-01T00:01:00Z",
                output={},
                summary={},
            )
        )
    )


def make_complete(
    call_id: str, project_id: str = "entity/project"
) -> CompleteBatchItem:
    """Helper to create a CompleteBatchItem for testing."""
    return CompleteBatchItem(
        req=tsi.CompletedCallSchemaForInsert(
            project_id=project_id,
            id=call_id,
            trace_id=f"trace_{call_id}",
            op_name="test_op",
            started_at="2024-01-01T00:00:00Z",
            inputs={},
            attributes={},
            ended_at="2024-01-01T00:01:00Z",
            output={},
            summary={},
        )
    )


# =============================================================================
# Pairing Behavior Tests
# =============================================================================


def test_start_end_pairing():
    """Test that starts and ends are paired into complete calls."""
    processed_batches = []

    def processor_fn(batch):
        processed_batches.append(batch)

    processor = CallBatchProcessor(
        processor_fn,
        max_batch_size=100,
        min_batch_interval=0.01,
    )

    # Enqueue start then end
    processor.enqueue([make_start("call_a")])
    processor.enqueue([make_end("call_a")])

    processor.stop_accepting_new_work_and_flush_queue()

    all_items = [item for batch in processed_batches for item in batch]
    assert len(all_items) == 1
    assert isinstance(all_items[0], CompleteBatchItem)
    assert all_items[0].req.id == "call_a"


def test_end_before_start_pairing():
    """Test that ends arriving before starts are still paired correctly."""
    processed_batches = []

    def processor_fn(batch):
        processed_batches.append(batch)

    processor = CallBatchProcessor(
        processor_fn,
        max_batch_size=100,
        min_batch_interval=0.01,
    )

    # Enqueue end before start (race condition scenario)
    processor.enqueue([make_end("call_b")])
    processor.enqueue([make_start("call_b")])

    processor.stop_accepting_new_work_and_flush_queue()

    all_items = [item for batch in processed_batches for item in batch]
    assert len(all_items) == 1
    assert isinstance(all_items[0], CompleteBatchItem)
    assert all_items[0].req.id == "call_b"


def test_already_complete_items_passed_through():
    """Test that pre-made complete items are passed through."""
    processed_batches = []

    def processor_fn(batch):
        processed_batches.append(batch)

    processor = CallBatchProcessor(
        processor_fn,
        max_batch_size=100,
        min_batch_interval=0.01,
    )

    processor.enqueue([make_complete("pre_complete")])

    processor.stop_accepting_new_work_and_flush_queue()

    all_items = [item for batch in processed_batches for item in batch]
    assert len(all_items) == 1
    assert isinstance(all_items[0], CompleteBatchItem)
    assert all_items[0].req.id == "pre_complete"


def test_multiple_pairing():
    """Test that multiple starts and ends are paired correctly."""
    processed_batches = []

    def processor_fn(batch):
        processed_batches.append(batch)

    processor = CallBatchProcessor(
        processor_fn,
        max_batch_size=100,
        min_batch_interval=0.01,
    )

    processor.enqueue([make_start("call_a")])
    processor.enqueue([make_start("call_b")])
    processor.enqueue([make_end("call_b")])  # out of order
    processor.enqueue([make_end("call_a")])

    processor.stop_accepting_new_work_and_flush_queue()

    all_items = [item for batch in processed_batches for item in batch]
    assert len(all_items) == 2
    assert all(isinstance(item, CompleteBatchItem) for item in all_items)
    ids = {item.req.id for item in all_items}
    assert ids == {"call_a", "call_b"}


# =============================================================================
# Unpaired Items on Shutdown
# =============================================================================


def test_unpaired_starts_dropped_on_shutdown():
    """Unpaired starts should be dropped (not sent) on shutdown."""
    processed_batches = []

    def processor_fn(batch):
        processed_batches.append(batch)

    processor = CallBatchProcessor(
        processor_fn,
        max_batch_size=100,
        min_batch_interval=0.01,
    )

    processor.enqueue([make_start("unpaired_start")])

    processor.stop_accepting_new_work_and_flush_queue()

    all_items = [item for batch in processed_batches for item in batch]
    # Unpaired starts are dropped, not sent
    assert len(all_items) == 0


def test_unpaired_ends_dropped_on_shutdown():
    """Unpaired ends should be dropped (not sent) on shutdown."""
    processed_batches = []

    def processor_fn(batch):
        processed_batches.append(batch)

    processor = CallBatchProcessor(
        processor_fn,
        max_batch_size=100,
        min_batch_interval=0.01,
    )

    processor.enqueue([make_end("unpaired_end")])

    processor.stop_accepting_new_work_and_flush_queue()

    all_items = [item for batch in processed_batches for item in batch]
    # Unpaired ends are dropped, not sent
    assert len(all_items) == 0


# =============================================================================
# Pending Limit Tests
# =============================================================================


def test_max_pending_calls_error():
    """Test that exceeding max_pending_calls raises an error."""
    processor = CallBatchProcessor(
        lambda batch: None,
        max_batch_size=100,
        min_batch_interval=0.01,
        max_pending_calls=3,
    )

    processor.enqueue([make_start("call_1")])
    processor.enqueue([make_start("call_2")])
    processor.enqueue([make_start("call_3")])

    with pytest.raises(RuntimeError, match="Too many pending calls"):
        processor.enqueue([make_start("call_4")])

    processor.stop_accepting_new_work_and_flush_queue()


def test_default_max_pending_calls():
    """Test that default max_pending_calls is set correctly."""
    processor = CallBatchProcessor(lambda batch: None)
    assert processor.max_pending_calls == DEFAULT_MAX_PENDING_CALLS
    processor.stop_accepting_new_work_and_flush_queue()


# =============================================================================
# num_outstanding_jobs / num_pending Tests
# =============================================================================


def test_num_outstanding_jobs_includes_pending():
    """num_outstanding_jobs should count both queue items and pending items."""
    processor = CallBatchProcessor(
        lambda batch: None,
        max_batch_size=100,
        min_batch_interval=10.0,  # Slow interval to keep items pending
    )

    processor.enqueue([make_start("call_1")])
    processor.enqueue([make_start("call_2")])

    # Should have 2 pending starts
    assert processor.num_outstanding_jobs >= 2
    assert processor.num_pending == 2

    processor.stop_accepting_new_work_and_flush_queue()


def test_num_pending_decreases_on_pairing():
    """num_pending should decrease when items are paired."""
    processor = CallBatchProcessor(
        lambda batch: None,
        max_batch_size=100,
        min_batch_interval=10.0,
    )

    processor.enqueue([make_start("call_1")])
    assert processor.num_pending == 1

    processor.enqueue([make_end("call_1")])
    # After pairing, pending should be 0 (item is now in queue)
    assert processor.num_pending == 0

    processor.stop_accepting_new_work_and_flush_queue()


# =============================================================================
# Null ID Handling
# =============================================================================


def test_start_with_none_id_dropped():
    """Starts with None id should be dropped (can't be paired)."""
    processed_batches = []

    def processor_fn(batch):
        processed_batches.append(batch)

    processor = CallBatchProcessor(
        processor_fn,
        max_batch_size=100,
        min_batch_interval=0.01,
    )

    start_no_id = StartBatchItem(
        req=tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id="entity/project",
                id=None,
                op_name="test_op",
                started_at="2024-01-01T00:00:00Z",
                inputs={},
                attributes={},
            )
        )
    )
    processor.enqueue([start_no_id])

    processor.stop_accepting_new_work_and_flush_queue()

    all_items = [item for batch in processed_batches for item in batch]
    # Starts with None id are dropped
    assert len(all_items) == 0
