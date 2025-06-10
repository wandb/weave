from __future__ import annotations

import time
from unittest.mock import MagicMock, call, patch

from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor


def test_max_batch_size():
    processor_fn = MagicMock()
    processor = AsyncBatchProcessor(processor_fn, max_batch_size=2)

    # Queue up 2 batches of 3 items
    processor.enqueue([1, 2, 3])
    processor.stop_accepting_new_work_and_flush_queue()

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
    processor.stop_accepting_new_work_and_flush_queue()

    # Processor should batch them all together
    processor_fn.assert_called_once_with([1, 2, 3, 4, 5, 6, 7, 8, 9])


def test_wait_until_all_processed():
    processor_fn = MagicMock()
    processor = AsyncBatchProcessor(
        processor_fn, max_batch_size=100, min_batch_interval=0.01
    )

    processor.enqueue([1, 2, 3])
    processor.stop_accepting_new_work_and_flush_queue()

    # Despite queueing extra items, they will never get flushed because the processor is
    # already shut down.
    processor.enqueue([4, 5, 6])
    processor.stop_accepting_new_work_and_flush_queue()
    processor.enqueue([7, 8, 9])
    processor.stop_accepting_new_work_and_flush_queue()

    # We should only see the first batch.  Everything else is stuck in the queue.
    processor_fn.assert_has_calls([call([1, 2, 3])])
    assert processor.queue.qsize() == 6


def test_health_check_thread_is_created():
    """Test that health check thread is created and running."""
    processor_fn = MagicMock()
    processor = AsyncBatchProcessor(
        processor_fn, max_batch_size=100, min_batch_interval=0.1
    )

    # Health check thread should be alive
    assert processor.health_check_thread.is_alive()
    assert processor.processing_thread.is_alive()

    processor.stop_accepting_new_work_and_flush_queue()

    assert not processor.health_check_thread.is_alive()
    assert not processor.processing_thread.is_alive()

    # restart thread
    processor.accept_new_work()
    assert processor.health_check_thread.is_alive()
    assert processor.processing_thread.is_alive()
    processor.stop_accepting_new_work_and_flush_queue()


def test_health_check_functionality_and_logging():
    """Test health check revival functionality, logging, and full queue behavior."""
    processor_fn = MagicMock()

    with patch(
        "weave.trace_server_bindings.async_batch_processor.logger"
    ) as mock_logger:
        # Create processor with small queue to test full queue behavior
        processor = AsyncBatchProcessor(
            processor_fn, max_batch_size=100, min_batch_interval=0.1, max_queue_size=1
        )

        # Test 1: Test the _ensure_health_check_alive method directly
        original_health_thread = processor.health_check_thread
        with patch.object(
            processor.health_check_thread, "is_alive", return_value=False
        ):
            processor._ensure_health_check_alive()

            # Should have created a new health check thread
            assert processor.health_check_thread != original_health_thread
            assert processor.health_check_thread.is_alive()
            mock_logger.warning.assert_called_with(
                "Health check thread died, attempting to revive it"
            )
            mock_logger.info.assert_called_with(
                "Health check thread successfully revived"
            )

        # Test 2: Health check revival on full queue
        mock_logger.reset_mock()
        with patch.object(
            processor.health_check_thread, "is_alive", return_value=False
        ):
            processor.enqueue([1])  # Fills the queue
            processor.enqueue([2])  # Should trigger Full exception

            assert processor.health_check_thread.is_alive()

        # Test 3: Health check stops when not accepting work
        assert processor.health_check_thread.is_alive()
        processor.stop_accepting_new_work_and_flush_queue()
        assert not processor.health_check_thread.is_alive()


def test_processing_thread_exception_handling():
    """Test that processing thread exceptions are handled and logged appropriately."""

    # Create a processor function that will raise an exception
    def failing_processor_fn(batch):
        raise RuntimeError("Simulated processing error")

    with patch(
        "weave.trace_server_bindings.async_batch_processor.logger"
    ) as mock_logger:
        processor = AsyncBatchProcessor(
            failing_processor_fn, max_batch_size=100, min_batch_interval=0.1
        )

        # Enqueue some items
        processor.enqueue([1, 2, 3])

        # Wait a bit for processing
        time.sleep(0.2)

        # Stop and check logs
        processor.stop_accepting_new_work_and_flush_queue()

        # Should have logged the exception
        mock_logger.exception.assert_called_with(
            "Error processing batch: Simulated processing error"
        )

        # make sure we can restart and everything is as expected
        processor.accept_new_work()
        processor.enqueue([1, 2, 3])
        assert processor.health_check_thread.is_alive()
        assert processor.processing_thread.is_alive()
        processor.stop_accepting_new_work_and_flush_queue()

        # Should have logged the exception
        mock_logger.exception.assert_called_with(
            "Error processing batch: Simulated processing error"
        )


def test_realistic_health_check_revival_scenario():
    """Test realistic scenario: process items successfully, thread dies, health check revives it."""
    processed_items = []

    def tracking_processor_fn(batch):
        """Processor that tracks what it processes."""
        processed_items.extend(batch)
        time.sleep(0.05)  # Simulate some processing time

    with patch(
        "weave.trace_server_bindings.async_batch_processor.logger"
    ) as mock_logger:
        # Use shorter intervals for faster testing
        with patch(
            "weave.trace_server_bindings.async_batch_processor.HEALTH_CHECK_INTERVAL",
            0.5,
        ):
            processor = AsyncBatchProcessor(
                tracking_processor_fn, max_batch_size=10, min_batch_interval=0.1
            )

            # Step 1: Process 5 items successfully
            processor.enqueue([1, 2, 3, 4, 5])
            time.sleep(0.3)  # Wait for processing

            # Verify initial processing worked
            assert len(processed_items) == 5
            assert processed_items == [1, 2, 3, 4, 5]
            assert processor.processing_thread.is_alive()
            assert processor.health_check_thread.is_alive()

            # Step 2: Kill the processing thread (simulate thread death)
            original_processing_thread = processor.processing_thread

            # Mock the processing thread to appear dead
            with patch.object(
                processor.processing_thread, "is_alive", return_value=False
            ):
                # Step 3: Immediately enqueue another item
                processor.enqueue([6])

                # Step 4: Initial assertions - item should be queued but not processed yet
                assert processor.num_outstanding_jobs == 1  # Item 6 is in queue
                assert len(processed_items) == 5  # Still only processed first 5 items
                assert not processor.processing_thread.is_alive()  # Thread appears dead

                # Step 5: Wait for health check cycle (0.5 seconds + a bit extra)
                time.sleep(0.7)

            # Step 6: Final assertions - health check should have revived the thread
            # Give a moment for the new thread to process the queued item
            time.sleep(0.2)

            # The processing thread should be different (new thread created)
            assert processor.processing_thread != original_processing_thread
            assert processor.processing_thread.is_alive()
            # Health check alive
            assert processor.health_check_thread.is_alive()

            # The queued item should have been processed
            assert len(processed_items) == 6
            assert processed_items[-1] == 6  # Item 6 was processed
            assert processor.num_outstanding_jobs == 0  # Queue is empty

            # Step 7: Test that everything continues to work normally
            processor.enqueue([7, 8, 9])
            time.sleep(0.2)

            assert len(processed_items) == 9
            assert processed_items[-3:] == [7, 8, 9]

            processor.stop_accepting_new_work_and_flush_queue()
