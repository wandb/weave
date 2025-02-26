from __future__ import annotations

import threading
import time
from unittest.mock import Mock, call

import pytest

from weave.trace_server.async_batch_processor import AsyncBatchProcessor


def test_enqueue_and_process():
    processor_fn = Mock()
    processor = AsyncBatchProcessor(
        processor_fn, max_batch_size=10, min_batch_interval=0.1
    )

    items = list(range(5))
    processor.enqueue(items)
    processor.wait_until_all_processed()

    assert processor_fn.call_count == 1
    assert processor_fn.call_args_list[0] == call(items)


def test_batch_size_limit():
    processor_fn = Mock()
    processor = AsyncBatchProcessor(
        processor_fn, max_batch_size=5, min_batch_interval=0.1
    )

    items = list(range(12))
    processor.enqueue(items)
    processor.wait_until_all_processed()

    assert processor_fn.call_count == 3
    assert processor_fn.call_args_list[0] == call(items[:5])
    assert processor_fn.call_args_list[1] == call(items[5:10])
    assert processor_fn.call_args_list[2] == call(items[10:])


def test_multiple_enqueues():
    processor_fn = Mock()
    processor = AsyncBatchProcessor(
        processor_fn, max_batch_size=10, min_batch_interval=0.1
    )

    # Enqueued quickly together, so they should be processed together
    processor.enqueue([1, 2])
    processor.enqueue([3, 4])
    processor.enqueue([5])
    processor.wait_until_all_processed()

    processor_fn.assert_called_once()
    assert processor_fn.call_args[0][0] == [1, 2, 3, 4, 5]


def test_empty_batch():
    processor_fn = Mock()
    processor = AsyncBatchProcessor(
        processor_fn, max_batch_size=10, min_batch_interval=0.1
    )

    # Enqueue an empty batch, so no work is done
    processor.enqueue([])
    processor.wait_until_all_processed()

    processor_fn.assert_not_called()


@pytest.mark.disable_logging_error_check
def test_error_handling_continues_processing():
    successful_items = []
    failed_items = []
    batch_count = 0

    def batch_counting_processor(items):
        nonlocal batch_count
        batch_count += 1

        # Track items based on success or failure
        if batch_count == 2:
            # Second batch fails
            failed_items.extend(items)
            raise ValueError("Test error on second batch")
        else:
            # Other batches succeed
            successful_items.extend(items)

    processor = AsyncBatchProcessor(
        batch_counting_processor, max_batch_size=5, min_batch_interval=0.1
    )

    # Create 14 items that will be split into 3 batches
    all_items = list(range(14))
    processor.enqueue(all_items)
    processor.wait_until_all_processed()

    # Verify batches were processed
    assert batch_count == 3
    assert successful_items == all_items[:5] + all_items[10:]  # Batches 1, 3
    assert failed_items == all_items[5:10]  # Batch 2

    # NOTE: In this current implementation, the processor does not retry failures!


def test_processor_blocking_affects_queue():
    """
    Tests that when a processor function blocks, the entire queue is effectively blocked.

    This test verifies that:
    1. When the processor function blocks on processing a batch, subsequent batches
       remain queued and unprocessed
    2. When the processor function unblocks, all queued batches are processed in order
    3. The queue size grows as more items are enqueued while processing is blocked

    This demonstrates the sequential processing behavior of the AsyncBatchProcessor
    and the potential for unbounded queue growth if processing is blocked indefinitely.
    """
    processed_items = []
    processing_event = threading.Event()

    def blocking_processor(items):
        processing_event.wait()  # Simulate blocking behaviour
        processed_items.extend(items)

    processor = AsyncBatchProcessor(
        blocking_processor, max_batch_size=3, min_batch_interval=0.1
    )

    # Phase 1: Enqueue items that will be blocked
    # ------------------------------------------
    first_batch = [1, 2, 3]
    processor.enqueue(first_batch)

    time.sleep(0.2)  # Let the processor pick up the first batch

    # Verify nothing has been processed yet (processor is blocked).
    # Initial queue size is 0 because the first batch has been picked up but is blocked
    assert not processed_items
    assert processor.queue.qsize() == 0

    # Phase 2: Enqueue more items while processor is blocked
    # ----------------------------------------------------
    second_batch = [4, 5, 6]
    third_batch = [7, 8, 9]
    processor.enqueue(second_batch)
    processor.enqueue(third_batch)

    # Verify still nothing processed (processor is blocked on the first batch).
    # Queue size has now increased to contain the new items.  This demonstrates how the
    # queue can grow unbounded if processing is blocked
    assert not processed_items
    assert processor.queue.qsize() == 6  # 2nd + 3rd batches stuck

    # Phase 3: Unblock the processor and verify all items are processed
    # ---------------------------------------------------------------
    processing_event.set()  # Now unblock the processor
    processor.wait_until_all_processed()  # Wait for all items to be processed

    # Verify all batches were processed in the correct order
    expected_items = first_batch + second_batch + third_batch
    assert processed_items == expected_items

    # Verify queue is now empty
    assert processor.queue.qsize() == 0
