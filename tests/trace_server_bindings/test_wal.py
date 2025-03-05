import atexit
import datetime
import os
import shutil
import tempfile
import threading
from unittest.mock import MagicMock, patch

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
from weave.trace_server_bindings.remote_http_trace_server import (
    EndBatchItem,
    StartBatchItem,
)
from weave.trace_server_bindings.sqlite_wal import SQLiteWriteAheadLog


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path)


def test_wal_basic_functionality(temp_dir):
    """Test basic WAL functionality - adding and retrieving items."""
    # Create a WAL
    wal_path = os.path.join(temp_dir, "test_wal.db")
    wal = SQLiteWriteAheadLog(wal_path)

    # Create test items
    start_req = tsi.CallStartReq(
        start=tsi.StartedCallSchemaForInsert(
            project_id="test-entity/test-project",
            op_name="test-call",
            started_at=datetime.datetime.now(),
            attributes={},
            inputs={"a": 1, "b": 2},
        )
    )

    end_req = tsi.CallEndReq(
        end=tsi.EndedCallSchemaForInsert(
            project_id="test-entity/test-project",
            id="test-call-id",
            ended_at=datetime.datetime.now(),
            output={"result": 3},
            summary={},
        )
    )

    start_item = StartBatchItem(req=start_req)
    end_item = EndBatchItem(req=end_req)

    # Add items to WAL
    wal.append([start_item, end_item])

    # Retrieve items
    items = wal.get_all_items()
    assert len(items) == 2, f"Expected 2 items in WAL, got {len(items)}"

    # Clear WAL
    wal.clear()

    # Verify WAL is empty
    items = wal.get_all_items()
    assert len(items) == 0, f"Expected WAL to be empty, got {len(items)} items"


def test_async_processor_with_wal(temp_dir):
    """Test that AsyncBatchProcessor correctly uses the WAL."""
    # Create a processor function that tracks processed items
    processed_items = []
    processed_event = threading.Event()

    def process_batch(batch):
        processed_items.extend(batch)
        processed_event.set()

    # Create processor with WAL
    wal_path = os.path.join(temp_dir, "test_processor_wal.db")
    processor = AsyncBatchProcessor(
        process_batch,
        max_batch_size=5,
        min_batch_interval=0.1,
        use_wal=True,
        wal_path=wal_path,
    )

    # Create test items
    start_req = tsi.CallStartReq(
        start=tsi.StartedCallSchemaForInsert(
            project_id="test-entity/test-project",
            op_name="test-call",
            started_at=datetime.datetime.now(),
            attributes={},
            inputs={"a": 1, "b": 2},
        )
    )

    end_req = tsi.CallEndReq(
        end=tsi.EndedCallSchemaForInsert(
            project_id="test-entity/test-project",
            id="test-call-id",
            ended_at=datetime.datetime.now(),
            output={"result": 3},
            summary={},
        )
    )

    start_item = StartBatchItem(req=start_req)
    end_item = EndBatchItem(req=end_req)

    # Add items to processor
    processor.enqueue([start_item, end_item])

    wal = SQLiteWriteAheadLog(wal_path)

    # After enqueue, check that no work has been done but items are in the WAL
    items = wal.get_all_items()
    assert len(items) == 2, f"Expected 2 items in WAL, got {len(items)}"
    assert len(processed_items) == 0, (
        f"Expected 0 items to be processed, got {len(processed_items)}"
    )

    # Wait for processing
    processed_event.wait(timeout=2.0)
    processor.stop_accepting_new_work_and_flush_queue()

    # After processing, check that work is done and WAL is empty
    items = wal.get_all_items()
    assert len(items) == 0, (
        f"Expected WAL to be empty after processing, got {len(items)} items"
    )
    assert len(processed_items) == 2, (
        f"Expected 2 items to be processed, got {len(processed_items)}"
    )


def test_wal_recovery_after_crash(temp_dir):
    """Test recovery from WAL after a simulated crash."""
    wal_path = os.path.join(temp_dir, "test_recovery_wal.db")

    # FIRST RUN: Add items, but simulate crash before processing.  Below, we patch
    # `threading.Thread.start` to do nothing, which means processing will never happen.
    # Data should still be written to the WAL, and we will try to recover on the next run.
    first_run_processor = MagicMock()
    with patch("threading.Thread.start") as mock_start:
        processor = AsyncBatchProcessor(
            first_run_processor,
            max_batch_size=5,
            min_batch_interval=0.1,
            use_wal=True,
            wal_path=wal_path,
        )

        # Test only: Unregister the atexit handler to avoid the error message when the test exits
        atexit.unregister(processor.stop_accepting_new_work_and_flush_queue)

        # Create test items
        items = []
        for i in range(5):
            start_req = tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id="test-entity/test-project",
                    op_name=f"call_{i}",
                    started_at=datetime.datetime.now(),
                    attributes={},
                    inputs={"value": i},
                )
            )

            end_req = tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id="test-entity/test-project",
                    id=f"call_{i}_id",
                    ended_at=datetime.datetime.now(),
                    output={"result": i * 2},
                    summary={},
                )
            )

            start_item = StartBatchItem(req=start_req)
            end_item = EndBatchItem(req=end_req)

            items.extend([start_item, end_item])

        # Add items to processor (they'll be written to WAL but not processed)
        for item in items:
            processor.enqueue([item])

        # Verify items were written to WAL
        wal = SQLiteWriteAheadLog(wal_path)
        stored_items = wal.get_all_items()
        assert len(stored_items) == 10, (
            f"Expected 10 items in WAL, got {len(stored_items)}"
        )

        # Simulate crash by not shutting down properly
        del processor

    # SECOND RUN: Create a new processor and verify recovery.  For simplicity, we just
    # verify that all items are processed by checking that they are added to a list.
    # Once complete, we can verify that the WAL is empty.
    processed_items = []
    processed_event = threading.Event()

    def process_batch(batch):
        processed_items.extend(batch)
        if len(processed_items) >= 10:
            processed_event.set()

    processor = AsyncBatchProcessor(
        process_batch,
        max_batch_size=5,
        min_batch_interval=0.1,
        use_wal=True,
        wal_path=wal_path,
    )

    # Wait for recovery and processing (note: this happens automatically on init)
    processed_event.wait(timeout=3.0)
    processor.stop_accepting_new_work_and_flush_queue()

    # Verify items were recovered and processed
    assert len(processed_items) == 10, (
        f"Expected 10 items to be recovered and processed, got {len(processed_items)}"
    )

    # Check WAL is empty after processing
    wal = SQLiteWriteAheadLog(wal_path)
    remaining_items = wal.get_all_items()
    assert len(remaining_items) == 0, (
        f"Expected WAL to be empty after recovery, got {len(remaining_items)} items"
    )


def test_wal_max_items(temp_dir):
    """Test that WAL correctly handles the max_items parameter."""
    # Create a temporary directory for the WAL database
    wal_path = os.path.join(temp_dir, "test_max_items_wal.db")

    # Create a WAL with max_items=5
    wal = SQLiteWriteAheadLog(wal_path, max_items=5)

    # Add 10 items
    for i in range(10):
        start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id="test-entity/test-project",
                op_name=f"call_{i}",
                started_at=datetime.datetime.now(),
                attributes={},
                inputs={"value": i},
            )
        )

        start_item = StartBatchItem(req=start_req)
        wal.append([start_item])

    # Check that only the most recent items are in the WAL
    items = wal.get_all_items()
    assert len(items) <= 5, (
        f"Expected at most 5 items in WAL due to max_items, got {len(items)}"
    )
