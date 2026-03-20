"""Tests for the WAL (Write-Ahead Log) feature.

Covers:
- Client writes to WAL when enabled
- Client works normally when WAL is disabled (default)
- WALManager lifecycle (write-only and with sender)
- build_trace_server_handlers and create_sender
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import weave
from weave.durability.wal import WAL_RECORD_TYPES
from weave.durability.wal_consumer import JSONLWALConsumer
from weave.durability.wal_manager import WALManager
from weave.durability.wal_sender import build_trace_server_handlers, create_sender
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


class TestWALDisabled:
    """Verify the client works normally when WAL is disabled (the default)."""

    def test_wal_is_none_by_default(self, client):
        """Default client should have _wal=None."""
        assert client._wal is None

    def test_publish_works_without_wal(self, client):
        """publish() should succeed and return a ref when WAL is disabled."""
        ref = weave.publish({"key": "value"}, name="no_wal_obj")
        assert ref is not None

    def test_dataset_publish_works_without_wal(self, client):
        """Dataset publish should succeed when WAL is disabled."""
        ds = weave.Dataset(name="no_wal_ds", rows=[{"x": 1}])
        ref = weave.publish(ds, name="no_wal_ds")
        assert ref is not None

    def test_flush_works_without_wal(self, client):
        """flush() should not raise when WAL is disabled."""
        weave.publish({"a": 1}, name="flush_obj")
        client.flush()


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


class TestWALManagerLifecycle:
    """Unit tests for WALManager without a full client."""

    def test_write_only_manager(self, tmp_path):
        """WALManager without sender writes records but doesn't drain them."""
        mgr = WALManager("test-entity", "test-project")
        # Override wal_dir to use tmp_path for isolation.
        mgr.wal_dir = str(tmp_path)
        from weave.durability.wal_directory_manager import FileWALDirectoryManager
        from weave.durability.wal_writer import JSONLWALWriter

        dir_mgr = FileWALDirectoryManager(str(tmp_path))
        mgr._writer = JSONLWALWriter(dir_mgr)

        from weave.trace_server import trace_server_interface as tsi

        mgr.write(
            "obj_create",
            tsi.ObjCreateReq(
                obj=tsi.ObjSchemaForInsert(
                    project_id="test-entity/test-project",
                    object_id="test_obj",
                    val={"hello": "world"},
                )
            ),
        )
        mgr.flush()

        records = _read_all_wal_records(tmp_path)
        assert len(records) >= 1
        assert records[0]["type"] == "obj_create"

        # No sender — files should still be on disk.
        assert len(list(tmp_path.glob("*.jsonl"))) >= 1
        mgr.close()

    def test_close_is_idempotent(self, tmp_path):
        """Calling close() multiple times should not raise."""
        mgr = WALManager("test-entity", "test-project")
        mgr.close()
        mgr.close()  # second call should be a no-op

    def test_close_with_sender_is_idempotent(self, wal_client_with_sender):
        """close() on a manager with sender should be safe to call twice."""
        client, _wal_dir = wal_client_with_sender
        client._wal.close()
        client._wal.close()  # should not raise


class TestBuildTraceServerHandlers:
    """Verify build_trace_server_handlers produces correct handlers."""

    def test_builds_handler_for_every_record_type(self):
        """Should produce a handler for each type in WAL_RECORD_TYPES."""
        mock_server = MagicMock()
        handlers = build_trace_server_handlers(mock_server)

        assert set(handlers.keys()) == set(WAL_RECORD_TYPES)

    def test_handler_calls_correct_server_method(self):
        """Each handler should call the matching method on the server."""
        mock_server = MagicMock()
        handlers = build_trace_server_handlers(mock_server)

        from weave.trace_server import trace_server_interface as tsi

        req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id="e/p",
                object_id="test",
                val={"x": 1},
            )
        )
        record = {"type": "obj_create", "req": req.model_dump(mode="json")}
        handlers["obj_create"](record)

        mock_server.obj_create.assert_called_once()
        call_arg = mock_server.obj_create.call_args[0][0]
        assert isinstance(call_arg, tsi.ObjCreateReq)
        assert call_arg.obj.object_id == "test"

    def test_handler_calls_table_create(self):
        """table_create handler should call server.table_create."""
        mock_server = MagicMock()
        handlers = build_trace_server_handlers(mock_server)

        from weave.trace_server import trace_server_interface as tsi

        req = tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id="e/p",
                rows=[{"val": {"x": 1}, "digest": "abc123"}],
            )
        )
        record = {"type": "table_create", "req": req.model_dump(mode="json")}
        handlers["table_create"](record)

        mock_server.table_create.assert_called_once()


class TestCreateSender:
    """Verify the create_sender factory wires things up correctly."""

    def test_returns_configured_sender(self, tmp_path):
        """create_sender should return a BackgroundWALSender ready to start."""
        mock_server = MagicMock()
        sender = create_sender(str(tmp_path), mock_server, poll_interval=0.5)

        from weave.durability.wal_sender import BackgroundWALSender

        assert isinstance(sender, BackgroundWALSender)
        assert sender._poll_interval == 0.5

    def test_sender_can_start_and_stop(self, tmp_path):
        """The created sender should be startable and stoppable."""
        mock_server = MagicMock()
        sender = create_sender(str(tmp_path), mock_server, poll_interval=0.1)
        sender.start()
        sender.stop()
