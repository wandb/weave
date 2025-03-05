import os
import tempfile

from pydantic import BaseModel

from weave.trace_server_bindings.sqlite_wal import SQLiteWriteAheadLog


class TestItem(BaseModel):
    id: str
    value: int


def test_sqlite_wal_basic():
    """Test basic functionality of the SQLite WAL."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        wal = SQLiteWriteAheadLog(db_path=db_path)

        # Test appending items
        items = [TestItem(id=f"item{i}", value=i) for i in range(5)]
        wal.append(items)

        # Test retrieving items
        retrieved_items = wal.get_all_items()
        assert len(retrieved_items) == 5

        # Check that the items were stored correctly
        for i, item in enumerate(retrieved_items):
            assert item["type"] == "TestItem"
            assert item["data"]["id"] == f"item{i}"
            assert item["data"]["value"] == i
            assert "_wal_id" in item["data"]

        # Test deleting items
        wal_ids = [item["data"]["_wal_id"] for item in retrieved_items]
        wal.delete_items(wal_ids[:2])

        # Check that items were deleted
        remaining_items = wal.get_all_items()
        assert len(remaining_items) == 3

        # Test clearing all items
        wal.clear()
        assert len(wal.get_all_items()) == 0


def test_sqlite_wal_max_items():
    """Test that the WAL respects the max_items limit."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        wal = SQLiteWriteAheadLog(db_path=db_path, max_items=10)

        # Add 20 items (twice the max)
        for i in range(20):
            items = [TestItem(id=f"item{i}", value=i)]
            wal.append(items)

        # Check that only the most recent 10 items are kept
        retrieved_items = wal.get_all_items()
        assert len(retrieved_items) == 10

        # Verify that the oldest items were removed
        ids = [item["data"]["id"] for item in retrieved_items]
        for i in range(10, 20):
            assert f"item{i}" in ids


def test_sqlite_wal_item_types():
    """Test filtering by item types."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        wal = SQLiteWriteAheadLog(db_path=db_path)

        class AnotherItem(BaseModel):
            name: str

        # Add items of different types
        test_items = [TestItem(id=f"item{i}", value=i) for i in range(5)]
        another_items = [AnotherItem(name=f"name{i}") for i in range(3)]

        wal.append(test_items)
        wal.append(another_items)

        # Test retrieving all items
        all_items = wal.get_all_items()
        assert len(all_items) == 8

        # Test filtering by item type
        test_items_filtered = wal.get_all_items(item_types=["TestItem"])
        assert len(test_items_filtered) == 5

        another_items_filtered = wal.get_all_items(item_types=["AnotherItem"])
        assert len(another_items_filtered) == 3


def test_sqlite_wal_persistence():
    """Test that the WAL persists data across instances."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")

        # Create a WAL and add items
        wal1 = SQLiteWriteAheadLog(db_path=db_path)
        items = [TestItem(id=f"item{i}", value=i) for i in range(5)]
        wal1.append(items)

        # Create a new WAL instance with the same path
        wal2 = SQLiteWriteAheadLog(db_path=db_path)

        # Check that the items are still there
        retrieved_items = wal2.get_all_items()
        assert len(retrieved_items) == 5

        # Add more items with the new instance
        more_items = [TestItem(id=f"more{i}", value=i + 10) for i in range(3)]
        wal2.append(more_items)

        # Check that all items are there
        all_items = wal2.get_all_items()
        assert len(all_items) == 8
