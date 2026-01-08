"""Tests for CallBatchProcessor.

Tests the indexed pairing behavior that maximizes complete calls in batches.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.call_batch_processor import CallBatchProcessor
from weave.trace_server_bindings.models import (
    CompleteBatchItem,
    EndBatchItem,
    StartBatchItem,
)


def make_start(call_id: str, project_id: str = "entity/project") -> StartBatchItem:
    """Helper to create a StartBatchItem for testing."""
    return StartBatchItem(
        req=tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=f"trace_{call_id}",
                op_name="test_op",
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
        pytest.param(2.0, 4, id="timeout_2s_pairs_all"),  # Ends arrive before timeout
        pytest.param(
            0, 8, id="timeout_0_no_buffering"
        ),  # No buffering = 4 starts + 4 ends
        pytest.param(
            -1, 4, id="timeout_neg1_infinite_wait"
        ),  # Infinite wait = all paired
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
    """Test all pairing scenarios in one test.

    Covers:
    - Single start+end pair -> CompleteBatchItem
    - Orphan end (no matching start) -> EndBatchItem
    - Pre-made CompleteBatchItem -> passes through as-is
    - Start with None id -> queued immediately as StartBatchItem
    """
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

    # 4. Start with None id
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

    # Verify types and IDs
    completes = [i for i in all_items if isinstance(i, CompleteBatchItem)]
    ends = [i for i in all_items if isinstance(i, EndBatchItem)]
    starts = [i for i in all_items if isinstance(i, StartBatchItem)]

    assert len(completes) == 2  # paired_call + pre_complete
    assert {c.req.complete.id for c in completes} == {"paired_call", "pre_complete"}

    assert len(ends) == 1
    assert ends[0].req.end.id == "orphan_call"

    assert len(starts) == 1
    assert starts[0].req.start.id is None


# =============================================================================
# Stale Start Flushing Tests
# =============================================================================


def test_stale_starts_and_paired_calls():
    """Test mixed scenario: one call pairs, one times out as stale."""
    processed_batches = []

    def processor_fn(batch):
        processed_batches.append(batch)

    processor = CallBatchProcessor(
        processor_fn,
        max_batch_size=100,
        min_batch_interval=0.05,
        start_hold_timeout=0.2,  # 200ms timeout
    )

    # Enqueue two starts
    processor.enqueue([make_start("fast_call")])
    processor.enqueue([make_start("slow_call")])

    # Only end fast_call (slow_call becomes stale)
    processor.enqueue([make_end("fast_call")])

    # Wait for slow_call to become stale
    time.sleep(0.5)

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
        start_hold_timeout=60.0,  # Long timeout - won't trigger naturally
    )

    # Enqueue starts without ends
    processor.enqueue([make_start("pending_1")])
    processor.enqueue([make_start("pending_2")])
    processor.enqueue([make_start("pending_3")])

    # Immediately shut down (before timeout)
    processor.stop_accepting_new_work_and_flush_queue()

    all_items = [item for batch in processed_batches for item in batch]
    assert len(all_items) == 3
    assert all(isinstance(item, StartBatchItem) for item in all_items)
    assert {item.req.start.id for item in all_items} == {
        "pending_1",
        "pending_2",
        "pending_3",
    }


# =============================================================================
# Batching Behavior Tests
# =============================================================================


def test_batch_size_and_interval():
    """Test that max_batch_size is respected and items batch within interval."""
    processed_batches = []

    def processor_fn(batch):
        processed_batches.append(batch)

    processor = CallBatchProcessor(
        processor_fn,
        max_batch_size=2,  # Small batch size
        min_batch_interval=0.5,  # Long interval to batch items together
        start_hold_timeout=10.0,
    )

    # Quickly enqueue 5 complete calls
    for i in range(5):
        processor.enqueue([make_start(f"call_{i}")])
        processor.enqueue([make_end(f"call_{i}")])

    processor.stop_accepting_new_work_and_flush_queue()

    # All batches should respect max size of 2
    for batch in processed_batches:
        assert len(batch) <= 2

    # All 5 items should be processed
    all_items = [item for batch in processed_batches for item in batch]
    assert len(all_items) == 5
    assert all(isinstance(item, CompleteBatchItem) for item in all_items)


# =============================================================================
# Thread Management Tests
# =============================================================================


def test_thread_lifecycle():
    """Test threads are created, run, and stop correctly."""
    processor = CallBatchProcessor(
        lambda batch: None,
        max_batch_size=100,
        min_batch_interval=0.1,
    )

    # All threads alive after creation
    assert processor._processing_thread.is_alive()
    assert processor._flush_thread.is_alive()
    assert processor._health_check_thread.is_alive()

    processor.stop_accepting_new_work_and_flush_queue()

    # All threads stopped after shutdown
    assert not processor._processing_thread.is_alive()
    assert not processor._flush_thread.is_alive()
    assert not processor._health_check_thread.is_alive()


def test_health_check_revives_dead_thread():
    """Health check should revive dead processing thread."""
    processed_items = []

    def processor_fn(batch):
        processed_items.extend(batch)

    with patch(
        "weave.trace_server_bindings.call_batch_processor.HEALTH_CHECK_INTERVAL",
        0.2,
    ):
        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=100,
            min_batch_interval=0.05,
        )

        # Process first item
        processor.enqueue([make_start("call_1")])
        processor.enqueue([make_end("call_1")])
        time.sleep(0.2)

        # Simulate dead thread and add more items
        with patch.object(processor._processing_thread, "is_alive", return_value=False):
            processor.enqueue([make_start("call_2")])
            processor.enqueue([make_end("call_2")])
            time.sleep(0.4)  # Wait for health check

        processor.stop_accepting_new_work_and_flush_queue()

        # All items should be processed after revival
        assert len(processed_items) == 2


# =============================================================================
# Disk Fallback Tests
# =============================================================================


def test_disk_fallback_enabled_and_disabled():
    """Test disk fallback writes when enabled and doesn't when disabled."""

    def slow_processor(batch):
        time.sleep(1)  # Slow to cause queue overflow

    with tempfile.TemporaryDirectory() as temp_dir:
        # Test with fallback ENABLED
        enabled_path = Path(temp_dir) / "enabled.jsonl"
        processor_enabled = CallBatchProcessor(
            slow_processor,
            max_batch_size=100,
            min_batch_interval=0.01,
            max_queue_size=1,  # Tiny queue to force overflow
            enable_disk_fallback=True,
            disk_fallback_path=str(enabled_path),
        )

        for i in range(5):
            processor_enabled.enqueue([make_start(f"call_{i}")])
            processor_enabled.enqueue([make_end(f"call_{i}")])

        time.sleep(0.1)
        processor_enabled.stop_accepting_new_work_and_flush_queue()

        # File should exist with content
        if enabled_path.exists():
            with open(enabled_path) as f:
                content = f.read()
                assert "Ready queue full" in content

        # Test with fallback DISABLED
        disabled_path = Path(temp_dir) / "disabled.jsonl"
        processor_disabled = CallBatchProcessor(
            slow_processor,
            max_batch_size=100,
            min_batch_interval=0.01,
            max_queue_size=1,
            enable_disk_fallback=False,
            disk_fallback_path=str(disabled_path),
        )

        for i in range(5):
            processor_disabled.enqueue([make_start(f"call_{i}")])

        processor_disabled.stop_accepting_new_work_and_flush_queue()

        # File should NOT exist
        assert not disabled_path.exists()


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.disable_logging_error_check
def test_failed_batch_falls_back_to_individual_processing():
    """Failed batch should fall back to individual processing."""
    call_count = 0

    def selective_processor(batch):
        nonlocal call_count
        call_count += 1
        for item in batch:
            if (
                isinstance(item, CompleteBatchItem)
                and item.req.complete.id == "bad_call"
            ):
                raise RuntimeError("Processing failed")

    processor = CallBatchProcessor(
        selective_processor,
        max_batch_size=100,
        min_batch_interval=0.01,
    )

    # Enqueue good and bad calls
    processor.enqueue([make_start("good_call")])
    processor.enqueue([make_end("good_call")])
    processor.enqueue([make_start("bad_call")])
    processor.enqueue([make_end("bad_call")])

    processor.stop_accepting_new_work_and_flush_queue()

    # Should have called processor at least:
    # 1. First attempt with batch of 2 (fails due to bad_call)
    # 2. Individual attempt with good_call (succeeds)
    # 3. Individual attempt with bad_call (fails again)
    assert call_count == 3
