"""Tests for CallBatchProcessor.

Tests the call-specific pairing behavior that extends AsyncBatchProcessor.
Base functionality (disk fallback, health checks, etc.) is tested in test_async_batch_processor.py
"""

from __future__ import annotations

import time

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.call_batch_processor import (
    MAX_CALL_START_DELAY,
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
        req=tsi.CallCompleteReq(
            complete=tsi.CompletedCallSchemaForInsert(
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
    )


# =============================================================================
# Pairing Behavior Tests
# =============================================================================


@pytest.mark.parametrize(
    ("start_hold_timeout", "expected_total"),
    [
        pytest.param(2.0, 4, id="timeout_2s_pairs_all"),
        pytest.param(0, 8, id="timeout_0_no_buffering"),
        pytest.param(-1, 4, id="timeout_neg1_infinite_wait"),
    ],
)
def test_start_hold_timeout_affects_pairing(
    start_hold_timeout: float,
    expected_total: int,
):
    """Test how start_hold_timeout affects pairing behavior."""
    processed_batches = []

    def processor_fn(batch):
        processed_batches.append(batch)

    processor = CallBatchProcessor(
        processor_fn,
        max_batch_size=4,
        min_batch_interval=0.5,
        start_hold_timeout=start_hold_timeout,
    )

    processor.enqueue([make_start("call_a")])
    processor.enqueue([make_start("call_b")])
    processor.enqueue([make_start("call_c")])
    processor.enqueue([make_start("call_d")])
    time.sleep(1)  # Flush thread runs every 1s
    processor.enqueue([make_end("call_d")])
    processor.enqueue([make_end("call_c")])
    processor.enqueue([make_end("call_b")])
    processor.enqueue([make_end("call_a")])

    processor.stop_accepting_new_work_and_flush_queue()

    all_items = [item for batch in processed_batches for item in batch]
    assert len(all_items) == expected_total


def test_pairing_behavior_comprehensive():
    """Test all pairing scenarios: paired, orphan end, pre-complete, start with None id."""
    processed_batches = []

    def processor_fn(batch):
        processed_batches.append(batch)

    processor = CallBatchProcessor(
        processor_fn,
        max_batch_size=100,
        min_batch_interval=0.01,
        start_hold_timeout=10.0,
    )

    # 1. Single start+end pair
    processor.enqueue([make_start("paired_call")])
    processor.enqueue([make_end("paired_call")])

    # 2. Orphan end (no matching start)
    processor.enqueue([make_end("orphan_call")])

    # 3. Pre-made complete
    processor.enqueue([make_complete("pre_complete")])

    # 4. Start with None id (queued immediately)
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
    assert len(all_items) == 4

    completes = [i for i in all_items if isinstance(i, CompleteBatchItem)]
    ends = [i for i in all_items if isinstance(i, EndBatchItem)]
    starts = [i for i in all_items if isinstance(i, StartBatchItem)]

    assert len(completes) == 2
    assert {c.req.complete.id for c in completes} == {"paired_call", "pre_complete"}
    assert len(ends) == 1
    assert ends[0].req.end.id == "orphan_call"
    assert len(starts) == 1
    assert starts[0].req.start.id is None


# =============================================================================
# MAX_CALL_START_DELAY Tests
# =============================================================================


def test_start_hold_timeout_capped_at_max():
    """Test that start_hold_timeout is capped at MAX_CALL_START_DELAY."""
    processor = CallBatchProcessor(lambda batch: None, start_hold_timeout=1000.0)
    assert processor.start_hold_timeout == MAX_CALL_START_DELAY
    processor.stop_accepting_new_work_and_flush_queue()


def test_start_hold_timeout_negative_not_capped():
    """Test that negative timeout (-1 = infinite) is not capped."""
    processor = CallBatchProcessor(lambda batch: None, start_hold_timeout=-1)
    assert processor.start_hold_timeout == -1
    processor.stop_accepting_new_work_and_flush_queue()


# =============================================================================
# Evaluation Op Special Handling
# =============================================================================


def test_evaluation_ops_never_buffered():
    """Test that evaluation ops are sent immediately, not buffered."""
    processed_batches = []

    def processor_fn(batch):
        processed_batches.append(batch)

    processor = CallBatchProcessor(
        processor_fn,
        max_batch_size=100,
        min_batch_interval=0.01,
        start_hold_timeout=60.0,
    )

    processor.enqueue([make_start("eval_call", op_name="Evaluation.evaluate")])
    assert "eval_call" not in processor._pending_starts

    processor.stop_accepting_new_work_and_flush_queue()

    all_items = [item for batch in processed_batches for item in batch]
    assert len(all_items) == 1
    assert isinstance(all_items[0], StartBatchItem)


# =============================================================================
# Stale Start Flushing Tests
# =============================================================================


def test_stale_starts_flushed_after_timeout():
    """Test that starts without matching ends are flushed after timeout."""
    processed_batches = []

    def processor_fn(batch):
        processed_batches.append(batch)

    processor = CallBatchProcessor(
        processor_fn,
        max_batch_size=100,
        min_batch_interval=0.05,
        start_hold_timeout=0.2,
    )

    processor.enqueue([make_start("fast_call")])
    processor.enqueue([make_start("slow_call")])
    processor.enqueue([make_end("fast_call")])

    time.sleep(0.5)  # Wait for slow_call to become stale

    processor.stop_accepting_new_work_and_flush_queue()

    all_items = [item for batch in processed_batches for item in batch]
    assert len(all_items) == 2

    completes = [i for i in all_items if isinstance(i, CompleteBatchItem)]
    starts = [i for i in all_items if isinstance(i, StartBatchItem)]

    assert len(completes) == 1
    assert completes[0].req.complete.id == "fast_call"
    assert len(starts) == 1
    assert starts[0].req.start.id == "slow_call"


def test_shutdown_flushes_pending_starts():
    """Shutdown should flush all pending starts regardless of timeout."""
    processed_batches = []

    def processor_fn(batch):
        processed_batches.append(batch)

    processor = CallBatchProcessor(
        processor_fn,
        max_batch_size=100,
        min_batch_interval=0.01,
        start_hold_timeout=60.0,
    )

    processor.enqueue([make_start("pending_1")])
    processor.enqueue([make_start("pending_2")])
    processor.enqueue([make_start("pending_3")])

    processor.stop_accepting_new_work_and_flush_queue()

    all_items = [item for batch in processed_batches for item in batch]
    assert len(all_items) == 3
    assert all(isinstance(item, StartBatchItem) for item in all_items)


# =============================================================================
# num_outstanding_jobs Test
# =============================================================================


def test_num_outstanding_jobs_includes_pending_starts():
    """num_outstanding_jobs should count both queue items and pending starts."""
    processor = CallBatchProcessor(
        lambda batch: time.sleep(10),  # Slow processor to keep items in queue
        max_batch_size=100,
        min_batch_interval=10.0,
        start_hold_timeout=60.0,
    )

    # Enqueue starts (go to pending_starts)
    processor.enqueue([make_start("call_1")])
    processor.enqueue([make_start("call_2")])

    # Should have 2 pending starts
    assert processor.num_outstanding_jobs == 2

    processor.stop_accepting_new_work_and_flush_queue()
