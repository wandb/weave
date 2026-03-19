"""Tests that WeaveClient writes requests to the WAL when enabled."""

from __future__ import annotations

import json
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
    """Create a client with WAL enabled and yield (client, wal_dir)."""
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
            # Should not raise — all records must be JSON-serializable
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

        # After flush, records should be readable
        records = _read_all_wal_records(wal_dir)
        assert len(records) >= 1
