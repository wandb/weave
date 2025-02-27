from __future__ import annotations

import time
from unittest.mock import MagicMock, call

from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor


def test_max_batch_size():
    processor_fn = MagicMock()
    processor = AsyncBatchProcessor(processor_fn, max_batch_size=2)

    # Queue up 2 batches of 3 items
    processor.enqueue([1, 2, 3])
    processor.stop_accepting_new_work_and_safely_shutdown()

    # But the max batch size is 2, so the batch is split apart
    processor_fn.assert_has_calls(
        [
            call([1, 2]),
            call([3]),
        ]
    )


def test_min_batch_interval():
    processor_fn = MagicMock()
    processor = AsyncBatchProcessor(
        processor_fn, max_batch_size=100, min_batch_interval=1
    )

    # Queue up batches of 3 items within the min_batch_interval
    processor.enqueue([1, 2, 3])
    time.sleep(0.1)
    processor.enqueue([4, 5, 6])
    time.sleep(0.1)
    processor.enqueue([7, 8, 9])
    processor.stop_accepting_new_work_and_safely_shutdown()

    # Processor should batch them all together
    processor_fn.assert_called_once_with([1, 2, 3, 4, 5, 6, 7, 8, 9])


def test_wait_until_all_processed():
    processor_fn = MagicMock()
    processor = AsyncBatchProcessor(
        processor_fn, max_batch_size=100, min_batch_interval=0.01
    )

    processor.enqueue([1, 2, 3])
    processor.stop_accepting_new_work_and_safely_shutdown()

    # Despite queueing extra items, they will never get flushed because the processor is
    # already shut down.
    processor.enqueue([4, 5, 6])
    processor.stop_accepting_new_work_and_safely_shutdown()
    processor.enqueue([7, 8, 9])
    processor.stop_accepting_new_work_and_safely_shutdown()

    # We should only see the first batch.  Everything else is stuck in the queue.
    processor_fn.assert_has_calls([call([1, 2, 3])])
    assert processor.queue.qsize() == 6


def test_overflow_queue():
    processor_fn = MagicMock()
    # Create a processor with a small max queue size to test overflow
    processor = AsyncBatchProcessor(
        processor_fn, max_batch_size=5, min_batch_interval=0.01, max_queue_size=3
    )

    # Enqueue more items than the queue can hold
    processor.enqueue([1, 2, 3, 4, 5, 6, 7, 8])

    # Wait a bit to allow processing
    time.sleep(0.1)

    # Stop the processor
    processor.stop_accepting_new_work_and_safely_shutdown()

    # Verify all items were processed, including those in the overflow queue
    # The exact batching might vary, but all items should be processed
    all_processed_items = []
    for call_args in processor_fn.call_args_list:
        all_processed_items.extend(call_args[0][0])

    assert sorted(all_processed_items) == [1, 2, 3, 4, 5, 6, 7, 8]

    # Verify the overflow queue is empty after processing
    assert len(processor.overflow_queue) == 0
