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


def make_start_req(name: str):
    return tsi.CallStartReq(
        start=tsi.StartedCallSchemaForInsert(
            project_id="test-entity/test-project",
            op_name=f"call_{name}",
            started_at=datetime.datetime.now(),
            attributes={},
            inputs={"value": name},
        )
    )


def make_end_req(name: str):
    return tsi.CallEndReq(
        end=tsi.EndedCallSchemaForInsert(
            project_id="test-entity/test-project",
            id=f"call_{name}_id",
            ended_at=datetime.datetime.now(),
            output={"result": name},
            summary={},
        )
    )


def test_basic_adding_and_reading_from_wal(temp_dir):
    # Create a WAL
    wal_path = os.path.join(temp_dir, "test_wal.db")
    wal = SQLiteWriteAheadLog(wal_path)

    # Create and append test items to WAL
    start_item = StartBatchItem(req=make_start_req("test-call"))
    end_item = EndBatchItem(req=make_end_req("test-call"))
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
    # Create a processor function that tracks processed items
    processed_items = []
    processed_event = threading.Event()

    def processor_fn(batch):
        processed_items.extend(batch)
        processed_event.set()

    # Create processor with WAL
    wal_path = os.path.join(temp_dir, "test_processor_wal.db")
    processor = AsyncBatchProcessor(
        processor_fn,
        max_batch_size=5,
        min_batch_interval=0.1,
        use_wal=True,
        wal_path=wal_path,
    )

    # Create and queue up test items
    start_item = StartBatchItem(req=make_start_req("test-call"))
    end_item = EndBatchItem(req=make_end_req("test-call"))
    processor.enqueue([start_item, end_item])

    # After enqueue, check that no work has been done but items are in the WAL
    items = processor.wal.get_all_items()
    assert len(items) == 2, f"Expected 2 items in WAL, got {len(items)}"
    assert len(processed_items) == 0, (
        f"Expected 0 items to be processed, got {len(processed_items)}"
    )

    # Wait for processing
    processed_event.wait(timeout=2.0)
    processor.stop_accepting_new_work_and_flush_queue()

    # After processing, check that work is done and WAL is empty
    items = processor.wal.get_all_items()
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
    with patch("threading.Thread.start"):
        processor = AsyncBatchProcessor(
            processor_fn=MagicMock(),
            max_batch_size=5,
            min_batch_interval=0.1,
            use_wal=True,
            wal_path=wal_path,
        )

        # Test only: Unregister the atexit handler to avoid the error message when the
        # test exits.  We need to do this because we are patching threading.Thread.start
        atexit.unregister(processor.stop_accepting_new_work_and_flush_queue)

        # Create and queue up test items
        for i in range(5):
            start_item = StartBatchItem(req=make_start_req(i))
            end_item = EndBatchItem(req=make_end_req(i))
            processor.enqueue([start_item, end_item])

        # Verify items were written to WAL
        stored_items = processor.wal.get_all_items()
        assert len(stored_items) == 10, (
            f"Expected 10 items in WAL, got {len(stored_items)}"
        )

        # Simulate crash by not shutting down properly
        del processor

        # If we inspect the WAL after crashing, we should see the same thing
        wal = SQLiteWriteAheadLog(wal_path)
        stored_items2 = wal.get_all_items()
        assert stored_items == stored_items2

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
    MAX_ITEMS = 2

    wal_path = os.path.join(temp_dir, "test_max_items_wal.db")
    wal = SQLiteWriteAheadLog(wal_path, max_items=MAX_ITEMS)

    for i in range(3):
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
    assert len(items) <= MAX_ITEMS, (
        f"Expected at most {MAX_ITEMS} items in WAL due to max_items, got {len(items)}"
    )
