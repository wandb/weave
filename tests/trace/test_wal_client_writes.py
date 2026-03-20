"""Tests that WeaveClient writes requests to the WAL when enabled."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import weave
from weave.durability.wal_consumer import JSONLWALConsumer
from weave.trace.settings import UserSettings


def _read_all_wal_records(wal_dir: Path) -> list[dict]:
    """Read all records from all WAL files in a directory."""
    records: list[dict] = []
    if not wal_dir.is_dir():
        return records
    for path in sorted(wal_dir.glob("*.jsonl")):
        consumer = JSONLWALConsumer(str(path))
        try:
            for entry in consumer.read_pending():
                records.append(entry.record)
        finally:
            consumer.close()
    return records


@pytest.fixture
def wal_client(client_creator):
    """Create a client with WAL enabled but sender stopped (write-only).

    Stops the background sender so records stay on disk for inspection.
    """
    stale_dir = Path.home() / ".weave" / "wal" / "shawn" / "test-project"
    if stale_dir.is_dir():
        shutil.rmtree(stale_dir)

    with client_creator(settings=UserSettings(enable_wal=True)) as client:
        # Stop the sender so it doesn't drain records while we inspect them.
        client._wal._sender.stop()
        client._wal._sender = None
        yield client, Path(client._wal.wal_dir)


@pytest.fixture
def wal_client_with_sender(client_creator):
    """Create a client with WAL enabled and sender running."""
    stale_dir = Path.home() / ".weave" / "wal" / "shawn" / "test-project"
    if stale_dir.is_dir():
        shutil.rmtree(stale_dir)

    with client_creator(settings=UserSettings(enable_wal=True)) as client:
        yield client, Path(client._wal.wal_dir)


class TestWALClientWrites:
    """Verify that client operations produce WAL records when enabled."""

    def test_obj_create(self, wal_client):
        client, wal_dir = wal_client

        weave.publish({"model": "gpt-4", "temp": 0.7}, name="my_obj")
        client._flush()

        records = _read_all_wal_records(wal_dir)
        obj_records = [r for r in records if r["type"] == "obj_create"]
        assert len(obj_records) >= 1
        req = obj_records[0]["req"]
        assert req["obj"]["object_id"] == "my_obj"
        assert req["obj"]["val"] is not None

    def test_table_create(self, wal_client):
        client, wal_dir = wal_client

        ds = weave.Dataset(name="test_ds", rows=[{"x": 1}, {"x": 2}])
        weave.publish(ds, name="test_ds")
        client._flush()

        records = _read_all_wal_records(wal_dir)
        table_records = [r for r in records if r["type"] == "table_create"]
        assert len(table_records) >= 1
        req = table_records[0]["req"]
        assert len(req["table"]["rows"]) == 2

    def test_wal_records_are_json_serializable(self, wal_client):
        """Ensure WAL records round-trip through JSON without error."""
        client, wal_dir = wal_client

        weave.publish({"nested": {"list": [1, 2, 3]}}, name="json_obj")
        client._flush()

        records = _read_all_wal_records(wal_dir)
        for record in records:
            roundtripped = json.loads(json.dumps(record))
            assert roundtripped["type"] in {
                "obj_create",
                "table_create",
                "file_create",
            }

    def test_flush_fsyncs_wal(self, wal_client):
        """flush() should fsync the WAL so records survive a process crash."""
        client, wal_dir = wal_client

        weave.publish({"a": 1}, name="fsync_obj")
        client.flush()

        records = _read_all_wal_records(wal_dir)
        assert len(records) >= 1


class TestWALSender:
    """Verify that the in-process sender drains WAL records automatically."""

    def test_sender_drains_on_close(self, wal_client_with_sender):
        """After close(), the sender's final drain should consume all records."""
        client, wal_dir = wal_client_with_sender

        weave.publish({"k": "v"}, name="sender_obj")
        client._flush()
        client._wal.close()

        remaining = list(wal_dir.glob("*.jsonl"))
        assert len(remaining) == 0

    def test_sender_drains_table_create(self, wal_client_with_sender):
        """Table-create records should be drained and files cleaned up."""
        client, wal_dir = wal_client_with_sender

        ds = weave.Dataset(name="sender_ds", rows=[{"x": 1}])
        weave.publish(ds, name="sender_ds")
        client._flush()
        client._wal.close()

        remaining = list(wal_dir.glob("*.jsonl"))
        assert len(remaining) == 0
