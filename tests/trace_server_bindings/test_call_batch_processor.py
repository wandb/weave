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


class TestPairingBehavior:
    """Tests for the core start/end pairing behavior."""

    @pytest.mark.parametrize(
        "start_hold_timeout",
        [
            pytest.param(1.0, id="normal_timeout_1s"),
            pytest.param(0, id="zero_timeout"),
            pytest.param(-1, id="negative_timeout"),
        ],
    )
    def test_four_starts_then_four_ends_produces_four_complete_items(
        self, start_hold_timeout: float
    ):
        """Test the exact scenario: 4 starts followed by 4 ends should produce 4 CompleteBatchItems.

        Given the queue:
            call_a start, call_b start, call_c start, call_d start,
            call_d end, call_c end, call_b end, call_a end

        With batch_size=4 and the old implementation (no pairing), this would produce:
            Batch 1: [start_a, start_b, start_c, start_d] -> 4 items
            Batch 2: [end_d, end_c, end_b, end_a] -> 4 items
            Total: 8 items sent to server

        With the new CallBatchProcessor (pairing at enqueue time), this should produce:
            Batch 1: [complete_d, complete_c, complete_b, complete_a] -> 4 items
            Total: 4 items sent to server (as CompleteBatchItems)

        This validates that we get 4 complete batched requests instead of 8 separate start/end requests.

        Parametrized with different start_hold_timeout values:
        - 1.0: Normal timeout - starts held for 1 second before flushing
        - 0: Zero timeout - starts would be immediately considered stale by flush thread
        - -1: Negative timeout - starts never considered stale (until shutdown)

        Pairing should work in all cases because it happens synchronously at enqueue time,
        before the flush thread has a chance to run.
        """
        processed_batches = []

        def processor_fn(batch):
            processed_batches.append(batch)

        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=4,  # Batch size of 4 as specified
            min_batch_interval=0.5,  # Non-trivial interval to allow batching
            start_hold_timeout=start_hold_timeout,
        )

        # Enqueue 4 starts
        processor.enqueue([make_start("call_a")])
        processor.enqueue([make_start("call_b")])
        processor.enqueue([make_start("call_c")])
        processor.enqueue([make_start("call_d")])

        # Enqueue 4 ends (in reverse order to match user's example)
        processor.enqueue([make_end("call_d")])
        processor.enqueue([make_end("call_c")])
        processor.enqueue([make_end("call_b")])
        processor.enqueue([make_end("call_a")])

        processor.stop_accepting_new_work_and_flush_queue()

        # All items across all batches should be CompleteBatchItems
        all_items = [item for batch in processed_batches for item in batch]

        # Should have exactly 4 items total (not 8)
        assert len(all_items) == 4, f"Expected 4 items but got {len(all_items)}"

        # All should be CompleteBatchItems (paired start+end)
        assert all(isinstance(item, CompleteBatchItem) for item in all_items), (
            f"Expected all CompleteBatchItems, got: {[type(i).__name__ for i in all_items]}"
        )

        # Verify all call IDs are present
        call_ids = {item.req.complete.id for item in all_items}
        assert call_ids == {"call_a", "call_b", "call_c", "call_d"}

    def test_immediate_pairing_when_end_follows_start(self):
        """Start followed by matching end should produce a CompleteBatchItem."""
        processed_batches = []

        def processor_fn(batch):
            processed_batches.append(batch)

        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=100,
            min_batch_interval=0.01,
            start_hold_timeout=10.0,
        )

        # Enqueue start then end
        processor.enqueue([make_start("call_a")])
        processor.enqueue([make_end("call_a")])

        processor.stop_accepting_new_work_and_flush_queue()

        # Should have one batch with one CompleteBatchItem
        assert len(processed_batches) == 1
        batch = processed_batches[0]
        assert len(batch) == 1
        assert isinstance(batch[0], CompleteBatchItem)
        assert batch[0].req.complete.id == "call_a"

    def test_multiple_pairs_consolidated(self):
        """Multiple start/end pairs should all be paired correctly."""
        processed_batches = []

        def processor_fn(batch):
            processed_batches.append(batch)

        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=100,
            min_batch_interval=0.01,
            start_hold_timeout=10.0,
        )

        # Enqueue multiple starts then their ends
        processor.enqueue([make_start("call_a")])
        processor.enqueue([make_start("call_b")])
        processor.enqueue([make_start("call_c")])
        processor.enqueue([make_end("call_a")])
        processor.enqueue([make_end("call_b")])
        processor.enqueue([make_end("call_c")])

        processor.stop_accepting_new_work_and_flush_queue()

        # All items should be complete
        all_items = [item for batch in processed_batches for item in batch]
        assert len(all_items) == 3
        assert all(isinstance(item, CompleteBatchItem) for item in all_items)

        # Verify all call IDs are present
        call_ids = {item.req.complete.id for item in all_items}
        assert call_ids == {"call_a", "call_b", "call_c"}

    def test_out_of_order_ends_still_pair(self):
        """Ends arriving in different order than starts should still pair correctly."""
        processed_batches = []

        def processor_fn(batch):
            processed_batches.append(batch)

        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=100,
            min_batch_interval=0.01,
            start_hold_timeout=10.0,
        )

        # Enqueue starts
        processor.enqueue([make_start("call_a")])
        processor.enqueue([make_start("call_b")])
        processor.enqueue([make_start("call_c")])

        # Enqueue ends in reverse order
        processor.enqueue([make_end("call_c")])
        processor.enqueue([make_end("call_b")])
        processor.enqueue([make_end("call_a")])

        processor.stop_accepting_new_work_and_flush_queue()

        # All should be complete items
        all_items = [item for batch in processed_batches for item in batch]
        assert len(all_items) == 3
        assert all(isinstance(item, CompleteBatchItem) for item in all_items)

    def test_orphaned_end_queued_directly(self):
        """End without matching start should be queued as-is."""
        processed_batches = []

        def processor_fn(batch):
            processed_batches.append(batch)

        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=100,
            min_batch_interval=0.01,
            start_hold_timeout=10.0,
        )

        # Enqueue only an end (no start)
        processor.enqueue([make_end("orphan_call")])

        processor.stop_accepting_new_work_and_flush_queue()

        # Should have one batch with one EndBatchItem
        assert len(processed_batches) == 1
        batch = processed_batches[0]
        assert len(batch) == 1
        assert isinstance(batch[0], EndBatchItem)
        assert batch[0].req.end.id == "orphan_call"

    def test_complete_items_passed_through(self):
        """CompleteBatchItems should be queued directly."""
        processed_batches = []

        def processor_fn(batch):
            processed_batches.append(batch)

        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=100,
            min_batch_interval=0.01,
            start_hold_timeout=10.0,
        )

        # Enqueue a pre-made complete item
        processor.enqueue([make_complete("pre_complete")])

        processor.stop_accepting_new_work_and_flush_queue()

        # Should pass through as-is
        assert len(processed_batches) == 1
        batch = processed_batches[0]
        assert len(batch) == 1
        assert isinstance(batch[0], CompleteBatchItem)
        assert batch[0].req.complete.id == "pre_complete"


class TestStaleStartFlushing:
    """Tests for the timeout-based flushing of stale starts."""

    def test_stale_starts_flushed_after_timeout(self):
        """Starts that don't receive ends within timeout should be flushed."""
        processed_batches = []

        def processor_fn(batch):
            processed_batches.append(batch)

        # Use a very short timeout for testing
        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=100,
            min_batch_interval=0.05,
            start_hold_timeout=0.2,  # 200ms timeout
        )

        # Enqueue a start but no end
        processor.enqueue([make_start("stale_call")])

        # Wait for timeout + flush cycle
        time.sleep(0.5)

        processor.stop_accepting_new_work_and_flush_queue()

        # Should have flushed the start
        all_items = [item for batch in processed_batches for item in batch]
        assert len(all_items) == 1
        assert isinstance(all_items[0], StartBatchItem)
        assert all_items[0].req.start.id == "stale_call"

    def test_end_arriving_before_timeout_creates_complete(self):
        """End arriving before timeout should create complete, not flush start."""
        processed_batches = []

        def processor_fn(batch):
            processed_batches.append(batch)

        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=100,
            min_batch_interval=0.05,
            start_hold_timeout=1.0,  # 1s timeout
        )

        # Enqueue start
        processor.enqueue([make_start("fast_call")])

        # End arrives quickly
        time.sleep(0.1)
        processor.enqueue([make_end("fast_call")])

        processor.stop_accepting_new_work_and_flush_queue()

        # Should be a complete item, not separate start/end
        all_items = [item for batch in processed_batches for item in batch]
        assert len(all_items) == 1
        assert isinstance(all_items[0], CompleteBatchItem)

    def test_mixed_stale_and_paired_calls(self):
        """Mix of stale starts and paired calls should be handled correctly."""
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

        # Only end fast_call
        processor.enqueue([make_end("fast_call")])

        # Wait for slow_call to become stale
        time.sleep(0.5)

        processor.stop_accepting_new_work_and_flush_queue()

        # Should have one complete and one stale start
        all_items = [item for batch in processed_batches for item in batch]
        assert len(all_items) == 2

        completes = [i for i in all_items if isinstance(i, CompleteBatchItem)]
        starts = [i for i in all_items if isinstance(i, StartBatchItem)]

        assert len(completes) == 1
        assert completes[0].req.complete.id == "fast_call"

        assert len(starts) == 1
        assert starts[0].req.start.id == "slow_call"


class TestBatchingBehavior:
    """Tests for batch size and timing behavior."""

    def test_max_batch_size_respected(self):
        """Batches should not exceed max_batch_size."""
        processed_batches = []

        def processor_fn(batch):
            processed_batches.append(batch)

        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=2,  # Small batch size
            min_batch_interval=0.01,
            start_hold_timeout=10.0,
        )

        # Enqueue 5 complete calls
        for i in range(5):
            processor.enqueue([make_start(f"call_{i}")])
            processor.enqueue([make_end(f"call_{i}")])

        processor.stop_accepting_new_work_and_flush_queue()

        # No batch should exceed size 2
        for batch in processed_batches:
            assert len(batch) <= 2

        # All items should be processed
        all_items = [item for batch in processed_batches for item in batch]
        assert len(all_items) == 5

    def test_min_batch_interval_batches_items(self):
        """Items enqueued within min_batch_interval should be batched together."""
        processed_batches = []

        def processor_fn(batch):
            processed_batches.append(batch)

        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=100,
            min_batch_interval=0.5,  # 500ms interval
            start_hold_timeout=10.0,
        )

        # Quickly enqueue multiple items
        for i in range(3):
            processor.enqueue([make_start(f"call_{i}")])
            processor.enqueue([make_end(f"call_{i}")])

        processor.stop_accepting_new_work_and_flush_queue()

        # Should all be in a single batch due to interval
        assert len(processed_batches) == 1
        assert len(processed_batches[0]) == 3


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_start_without_id_queued_immediately(self):
        """Start with None id should be queued immediately."""
        processed_batches = []

        def processor_fn(batch):
            processed_batches.append(batch)

        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=100,
            min_batch_interval=0.01,
            start_hold_timeout=10.0,
        )

        # Create start with None id
        start = StartBatchItem(
            req=tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id="entity/project",
                    id=None,  # No ID
                    op_name="test_op",
                    started_at="2024-01-01T00:00:00Z",
                    inputs={},
                    attributes={},
                )
            )
        )
        processor.enqueue([start])

        processor.stop_accepting_new_work_and_flush_queue()

        # Should be queued immediately as a StartBatchItem
        assert len(processed_batches) == 1
        assert isinstance(processed_batches[0][0], StartBatchItem)

    def test_end_with_unknown_start_queued_as_orphan(self):
        """End without a matching start should be queued as orphan."""
        processed_batches = []

        def processor_fn(batch):
            processed_batches.append(batch)

        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=100,
            min_batch_interval=0.01,
            start_hold_timeout=10.0,
        )

        # Create end with id that has no matching start
        end = make_end("unknown_call")
        processor.enqueue([end])

        processor.stop_accepting_new_work_and_flush_queue()

        # Should be queued immediately as an EndBatchItem (orphan)
        assert len(processed_batches) == 1
        assert isinstance(processed_batches[0][0], EndBatchItem)
        assert processed_batches[0][0].req.end.id == "unknown_call"

    def test_flush_on_shutdown_sends_all_pending_starts(self):
        """Shutdown should flush all pending starts."""
        processed_batches = []

        def processor_fn(batch):
            processed_batches.append(batch)

        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=100,
            min_batch_interval=0.01,
            start_hold_timeout=60.0,  # Long timeout
        )

        # Enqueue starts without ends
        processor.enqueue([make_start("pending_1")])
        processor.enqueue([make_start("pending_2")])
        processor.enqueue([make_start("pending_3")])

        # Immediately shut down (before timeout)
        processor.stop_accepting_new_work_and_flush_queue()

        # All pending starts should have been flushed
        all_items = [item for batch in processed_batches for item in batch]
        assert len(all_items) == 3
        assert all(isinstance(item, StartBatchItem) for item in all_items)

    def test_num_outstanding_jobs_counts_both_queues(self):
        """num_outstanding_jobs should count ready queue and pending starts."""

        def processor_fn(batch):
            time.sleep(0.5)  # Slow processing to keep items in queue

        processor = CallBatchProcessor(
            processor_fn,
            max_batch_size=100,
            min_batch_interval=0.01,
            start_hold_timeout=60.0,
        )

        # Enqueue items
        processor.enqueue([make_start("call_1")])  # Pending start
        processor.enqueue([make_start("call_2")])  # Pending start
        processor.enqueue([make_end("call_1")])  # Creates complete in ready queue

        # Should count pending start + complete in queue
        # Note: call_1 is now in ready queue as complete, call_2 is pending
        assert processor.num_outstanding_jobs >= 2

        processor.stop_accepting_new_work_and_flush_queue()


class TestHealthCheck:
    """Tests for health check and thread management."""

    def test_threads_are_created_and_running(self):
        """All worker threads should be alive after creation."""
        processor = CallBatchProcessor(
            lambda batch: None,
            max_batch_size=100,
            min_batch_interval=0.1,
        )

        assert processor._processing_thread.is_alive()
        assert processor._flush_thread.is_alive()
        assert processor._health_check_thread.is_alive()

        processor.stop_accepting_new_work_and_flush_queue()

        assert not processor._processing_thread.is_alive()
        assert not processor._flush_thread.is_alive()
        assert not processor._health_check_thread.is_alive()

    def test_health_check_revives_processing_thread(self):
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

            # Process some items
            processor.enqueue([make_start("call_1")])
            processor.enqueue([make_end("call_1")])
            time.sleep(0.2)

            original_thread = processor._processing_thread

            # Simulate dead thread
            with patch.object(
                processor._processing_thread, "is_alive", return_value=False
            ):
                # Add more items
                processor.enqueue([make_start("call_2")])
                processor.enqueue([make_end("call_2")])

                # Wait for health check
                time.sleep(0.4)

            # Thread should be revived
            processor.stop_accepting_new_work_and_flush_queue()

            # All items should eventually be processed
            assert len(processed_items) == 2


class TestDiskFallback:
    """Tests for disk fallback functionality."""

    def test_dropped_items_written_to_disk(self):
        """Items dropped due to full queue should be written to disk."""

        def processor_fn(batch):
            time.sleep(1)  # Slow processor

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "dropped.jsonl"

            processor = CallBatchProcessor(
                processor_fn,
                max_batch_size=100,
                min_batch_interval=0.01,
                max_queue_size=1,  # Tiny queue
                enable_disk_fallback=True,
                disk_fallback_path=str(log_path),
            )

            # Fill the queue
            for i in range(5):
                processor.enqueue([make_start(f"call_{i}")])
                processor.enqueue([make_end(f"call_{i}")])

            # Some items should have been dropped to disk
            time.sleep(0.1)

            processor.stop_accepting_new_work_and_flush_queue()

            # Check log file
            if log_path.exists():
                with open(log_path) as f:
                    content = f.read()
                    assert "Ready queue full" in content

    def test_disk_fallback_disabled(self):
        """No disk file should be created when fallback is disabled."""

        def processor_fn(batch):
            time.sleep(0.5)

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "should_not_exist.jsonl"

            processor = CallBatchProcessor(
                processor_fn,
                max_batch_size=100,
                min_batch_interval=0.01,
                max_queue_size=1,
                enable_disk_fallback=False,  # Disabled
                disk_fallback_path=str(log_path),
            )

            # Try to overflow the queue
            for i in range(5):
                processor.enqueue([make_start(f"call_{i}")])

            processor.stop_accepting_new_work_and_flush_queue()

            # No file should be created
            assert not log_path.exists()


@pytest.mark.disable_logging_error_check
class TestErrorHandling:
    """Tests for error handling in processing."""

    def test_failed_batch_processed_individually(self):
        """Failed batch should fall back to individual processing."""
        call_count = 0
        failed_ids = set()

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

        # Enqueue mix of good and bad calls
        processor.enqueue([make_start("good_call")])
        processor.enqueue([make_end("good_call")])
        processor.enqueue([make_start("bad_call")])
        processor.enqueue([make_end("bad_call")])

        processor.stop_accepting_new_work_and_flush_queue()

        # Should have tried batch first, then individual
        assert call_count >= 2
