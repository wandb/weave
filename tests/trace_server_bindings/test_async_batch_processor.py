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
