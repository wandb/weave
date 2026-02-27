from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

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


@pytest.mark.disable_logging_error_check
def test_processing_thread_exception_handling():
    """Test that processing thread exceptions are handled and logged appropriately."""

    # Create a processor function that will raise an exception
    def failing_processor_fn(batch):
        raise RuntimeError("Simulated processing error")

    with patch("weave.telemetry.trace_sentry.logger") as mock_logger:
        processor = AsyncBatchProcessor(
            failing_processor_fn,
            max_batch_size=100,
            min_batch_interval=0.1,
        )

        # Enqueue some items
        processor.enqueue([1, 2, 3])

        # Wait a bit for processing
        time.sleep(0.2)

        # Stop and check logs
        processor.stop_accepting_new_work_and_flush_queue()
        assert (
            "Unprocessable item detected, dropping item permanently."
            in mock_logger.exception.call_args[0][0]
        )

        # make sure we can restart and everything is as expected
        processor.accept_new_work()
        processor.enqueue([1, 2, 3])
        assert processor.health_check_thread.is_alive()
        assert processor.processing_thread.is_alive()
        processor.stop_accepting_new_work_and_flush_queue()


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
                tracking_processor_fn,
                max_batch_size=10,
                min_batch_interval=0.1,
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


@pytest.mark.disable_logging_error_check
def test_poison_pill_detection_and_immediate_drop():
    """Test poison pill detection and immediate dropping of failed items."""
    # Track what gets processed successfully
    successful_items = []

    poison_const = "poison_pill"
    batch_killer_const = "batch_killer"

    # Create processor that fails on specific items
    def selective_failing_processor(batch):
        nonlocal successful_items
        processed = []
        for item in batch:
            if item == poison_const:
                raise RuntimeError("Poison pill error")
            elif item == batch_killer_const:
                raise RuntimeError("Batch processing error")
            processed.append(item)

        successful_items += processed

    with tempfile.TemporaryDirectory() as temp_dir:
        log_path = Path(temp_dir) / "poison_test.jsonl"

        processor = AsyncBatchProcessor(
            selective_failing_processor,
            max_batch_size=10,
            min_batch_interval=0.1,
            max_queue_size=5,
            enable_disk_fallback=True,
            disk_fallback_path=str(log_path),
        )

        # Test 1: Successful processing (baseline)
        processor.enqueue(["good1", "good2"])
        time.sleep(0.2)
        assert successful_items == ["good1", "good2"]

        # Test 2: Batch failure triggers individual processing - some items succeed, poison pills are immediately dropped
        processor.enqueue(["good3", poison_const, batch_killer_const, "good4"])
        time.sleep(0.3)

        # good3 and good4 should succeed, poison_pill and batch_killer should be immediately dropped
        assert successful_items == ["good1", "good2", "good3", "good4"]

        # Test 3: Check poison pills were written to disk immediately
        assert log_path.exists()
        with open(log_path, encoding="utf-8") as f:
            log_content = f.read()
            assert "Unprocessable item detected" in log_content
            # Should have two poison pills logged (poison_const and batch_killer_const)
            assert log_content.count("Unprocessable item detected") == 2

        # Test 4: Queue full - items get written to disk instead of being enqueued
        # Stop the processor so nothing drains the queue during this test.
        # This makes the overflow behavior deterministic.
        processor.stop_accepting_new_work_and_flush_queue()

        # Now enqueue items - with no processing thread running, fill1-fill5 will
        # fill the queue, and fill6-fill7 will overflow.
        processor.enqueue(
            ["fill1", "fill2", "fill3", "fill4", "fill5", "fill6", "fill7"]
        )  # Fill the small queue (maxsize=5)

        # Confirm extras got written to disk
        with open(log_path, encoding="utf-8") as f:
            log_content = f.read().splitlines()
            # Should have 4 log entries: 2 poison pills + 2 queue full items (fill6, fill7)
            assert len(log_content) == 4
            # Check that queue full items were logged
            queue_full_entries = [
                line for line in log_content if "Queue is full" in line
            ]
            assert len(queue_full_entries) == 2

        # Test 5: Disk fallback disabled - no files should be written
        processor_no_disk = AsyncBatchProcessor(
            selective_failing_processor,
            enable_disk_fallback=False,  # Disabled
            disk_fallback_path=str(Path(temp_dir) / "should_not_exist.jsonl"),
        )

        processor_no_disk.enqueue([poison_const])
        time.sleep(0.3)
        processor_no_disk.enqueue(["1", "2", "3", "4", "5", "6", "7"])
        time.sleep(0.3)

        # No disk file should be created when disk fallback is disabled
        assert not Path(temp_dir, "should_not_exist.jsonl").exists()

        # cleanup
        processor.stop_accepting_new_work_and_flush_queue()
        processor_no_disk.stop_accepting_new_work_and_flush_queue()


def test_log_rotation_and_disk_fallback():
    """Test log file rotation, backup management, and disk operation error handling."""

    def simple_processor(batch):
        # Simple processor that always succeeds
        pass

    with tempfile.TemporaryDirectory() as temp_dir:
        log_path = Path(temp_dir) / "rotation_test.jsonl"

        # Mock the constants to make testing faster
        with (
            patch(
                "weave.trace_server_bindings.async_batch_processor.MAX_LOG_FILE_SIZE_BYTES",
                200,
            ),
            patch("weave.trace_server_bindings.async_batch_processor.MAX_LOGFILES", 2),
        ):
            processor = AsyncBatchProcessor(
                simple_processor,
                enable_disk_fallback=True,
                disk_fallback_path=str(log_path),
            )

            # Test 1: Fill up the log file to trigger rotation
            # Add enough items to exceed the mocked 200 byte limit
            large_items = [
                f"large_item_{i}" * 10 for i in range(10)
            ]  # Make items large
            for item in large_items:
                processor._write_item_to_disk(item, "Test rotation trigger")

            # Check that rotation occurred - backup file should exist
            backup_path = log_path.with_suffix(".1")
            assert backup_path.exists(), "Log rotation should create backup file"

            # Test 2: Continue adding to trigger multiple rotations
            more_large_items = [f"rotation_test_{i}" * 15 for i in range(10)]
            for item in more_large_items:
                processor._write_item_to_disk(item, "Multiple rotation test")

            # Check max backup files limit (should only keep MAX_LOGFILES-1 backups)
            backup2_path = log_path.with_suffix(".2")
            backup3_path = log_path.with_suffix(
                ".3"
            )  # Should not exist due to MAX_LOGFILES=2

            assert log_path.exists(), "Main log file should exist"
            assert backup_path.exists(), "First backup should exist"
            assert not backup3_path.exists(), "Should not exceed MAX_LOGFILES limit"

            # Test 3: Error handling in disk operations
            with (
                patch("builtins.open", side_effect=PermissionError("No write access")),
                patch("weave.telemetry.trace_sentry.logger") as mock_logger,
            ):
                processor._write_item_to_disk("test_item", "Permission test")

                # Should log the disk write failure
                mock_logger.exception.assert_called_with(
                    f"Failed to write dropped item {id('test_item')} to disk: No write access"
                )

            # Test 4: Log rotation failure handling
            # First ensure the log file exists and has enough content to trigger rotation
            # Add multiple large items to exceed the 200 byte limit
            for i in range(5):
                processor._write_item_to_disk(
                    f"large_setup_item_{i}" * 20, "Setup for rename failure test"
                )

            # Verify file exists and is large enough before testing rename failure
            assert log_path.exists(), (
                "Log file should exist before testing rename failure"
            )
            assert log_path.stat().st_size > 200, (
                "Log file should be large enough to trigger rotation"
            )

            # Mock pathlib.Path.rename at the class level to simulate a rename failure
            with (
                patch("pathlib.Path.rename", side_effect=OSError("Rename failed")),
                patch("weave.telemetry.trace_sentry.logger") as mock_logger,
            ):
                processor._rotate_log_file_if_needed()

                # Should handle rotation errors gracefully
                mock_logger.exception.assert_called()
                error_call_args = mock_logger.exception.call_args[0][0]
                assert "Failed to rotate log file" in error_call_args

            # Test 5: Directory creation during disk fallback
            nested_log_path = Path(temp_dir) / "nested" / "deep" / "test.jsonl"
            processor_nested = AsyncBatchProcessor(
                simple_processor,
                enable_disk_fallback=True,
                disk_fallback_path=str(nested_log_path),
            )

            # Should create nested directories automatically
            processor_nested._write_item_to_disk(
                "test_nested", "Directory creation test"
            )
            assert nested_log_path.exists(), "Should create nested directories"
            assert nested_log_path.parent.exists(), (
                "Parent directories should be created"
            )

            processor.stop_accepting_new_work_and_flush_queue()
            processor_nested.stop_accepting_new_work_and_flush_queue()
