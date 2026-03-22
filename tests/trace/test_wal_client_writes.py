"""Tests for the WAL (Write-Ahead Log) feature.

Covers:
- Client writes to WAL when enabled
- Client works normally when WAL is disabled (default)
- WALManager lifecycle (write-only and with sender)
- TraceServerHandlers and create_sender
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

import weave
from weave.durability.wal_consumer import JSONLWALConsumer
from weave.durability.wal_directory_manager import FileWALDirectoryManager
from weave.durability.wal_manager import WALManager
from weave.durability.wal_sender import (
    _RECORD_TYPE_TO_REQ,
    BackgroundWALSender,
    TraceServerHandlers,
    build_trace_server_handlers,
    create_sender,
)
from weave.durability.wal_writer import JSONLWALWriter
from weave.trace.settings import UserSettings
from weave.trace_server import trace_server_interface as tsi


def _read_all_wal_records(client: weave.WeaveClient) -> list[dict]:
    """Read all records from a client's WAL directory."""
    wal_dir = Path(client._wal.wal_dir)
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


def _redirect_wal_to(client: weave.WeaveClient, wal_dir: str) -> None:
    """Replace the client's WAL writer (and optionally sender) to use *wal_dir*.

    This gives each test an isolated WAL directory so parallel xdist
    workers never interfere with each other.
    """
    wal = client._wal
    # Tear down whatever was created during init.
    wal.close()
    # Re-create writer (and optionally sender) in the isolated directory.
    wal.wal_dir = wal_dir
    dir_mgr = FileWALDirectoryManager(wal_dir)
    wal._writer = JSONLWALWriter(dir_mgr)


@pytest.fixture
def wal_client(client_creator, tmp_path):
    """Create a client with WAL enabled but sender stopped (write-only).

    Redirects the WAL to ``tmp_path`` for test isolation.
    """
    wal_dir = str(tmp_path / "wal")
    with client_creator(settings=UserSettings(enable_wal=True)) as client:
        _redirect_wal_to(client, wal_dir)
        yield client


@pytest.fixture
def wal_client_with_sender(client_creator, tmp_path):
    """Create a client with WAL enabled and sender running.

    Redirects the WAL to ``tmp_path`` for test isolation.
    """
    wal_dir = str(tmp_path / "wal")
    with client_creator(settings=UserSettings(enable_wal=True)) as client:
        _redirect_wal_to(client, wal_dir)
        # Re-create sender pointing at the isolated directory.
        client._wal._sender = create_sender(wal_dir, client.server)
        client._wal._sender.start()
        yield client


class TestWALClientWrites:
    """Verify that client operations produce WAL records when enabled."""

    def test_obj_create(self, wal_client):
        weave.publish({"model": "gpt-4", "temp": 0.7}, name="my_obj")
        wal_client._flush()

        records = _read_all_wal_records(wal_client)
        assert len(records) == 1
        project_id = f"{wal_client.entity}/{wal_client.project}"
        assert records[0] == {
            "type": "obj_create",
            "req": {
                "obj": {
                    "project_id": project_id,
                    "object_id": "my_obj",
                    "val": {"model": "gpt-4", "temp": 0.7},
                    "builtin_object_class": None,
                    "expected_digest": None,
                    "wb_user_id": None,
                }
            },
        }

    def test_table_create(self, wal_client):
        wal_client._send_table_create([{"x": 1}, {"x": 2}])
        wal_client._flush()

        records = _read_all_wal_records(wal_client)
        project_id = f"{wal_client.entity}/{wal_client.project}"

        assert len(records) == 1
        assert records[0] == {
            "type": "table_create",
            "req": {
                "table": {
                    "project_id": project_id,
                    "rows": [{"x": 1}, {"x": 2}],
                    "expected_digest": None,
                }
            },
        }

    def test_file_create(self, wal_client):
        img = Image.new("RGB", (2, 2), color="red")
        weave.publish(img, name="my_image")
        wal_client._flush()

        records = _read_all_wal_records(wal_client)
        project_id = f"{wal_client.entity}/{wal_client.project}"

        # Image publish produces: 1 file_create (op code) + 1 obj_create (load op)
        # + 1 obj_create (image object).  The file_create for the image.png
        # binary is embedded within the image obj_create's val.files.
        assert len(records) == 3
        file_rec = records[0]
        assert file_rec["type"] == "file_create"
        assert file_rec["req"]["project_id"] == project_id
        assert file_rec["req"]["name"] == "obj.py"

        image_obj = records[2]
        assert image_obj["type"] == "obj_create"
        assert image_obj["req"]["obj"]["object_id"] == "my_image"
        assert image_obj["req"]["obj"]["val"]["weave_type"] == {
            "type": "PIL.Image.Image"
        }

    def test_call_start(self, wal_client):
        """Calling an op should produce a call_start WAL record with all fields."""

        @weave.op
        def add(a: int, b: int) -> int:
            return a + b

        add(1, 2)
        wal_client._flush()

        records = _read_all_wal_records(wal_client)
        project_id = f"{wal_client.entity}/{wal_client.project}"

        call_starts = [r for r in records if r["type"] == "call_start"]
        assert len(call_starts) == 1

        start = call_starts[0]["req"]["start"]
        assert start["project_id"] == project_id
        assert "/op/add:" in start["op_name"]
        assert start["inputs"] == {"a": 1, "b": 2}
        assert start["id"] is not None
        assert start["trace_id"] is not None
        assert start["started_at"] is not None
        assert isinstance(start["attributes"], dict)
        assert start["parent_id"] is None  # root call

    def test_call_end(self, wal_client):
        """Calling an op should produce a call_end WAL record with all fields."""

        @weave.op
        def add(a: int, b: int) -> int:
            return a + b

        add(1, 2)
        wal_client._flush()

        records = _read_all_wal_records(wal_client)
        project_id = f"{wal_client.entity}/{wal_client.project}"

        call_ends = [r for r in records if r["type"] == "call_end"]
        assert len(call_ends) == 1

        end = call_ends[0]["req"]["end"]
        assert end["project_id"] == project_id
        assert end["id"] is not None
        assert end["output"] == 3
        assert end["ended_at"] is not None
        assert end["exception"] is None
        assert isinstance(end["summary"], dict)

    def test_call_with_exception(self, wal_client):
        """A failing op should record the exception in call_end."""

        @weave.op
        def fail() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            fail()
        wal_client._flush()

        records = _read_all_wal_records(wal_client)

        call_ends = [r for r in records if r["type"] == "call_end"]
        assert len(call_ends) == 1
        assert "boom" in call_ends[0]["req"]["end"]["exception"]

    def test_nested_calls(self, wal_client):
        """Nested op calls should produce parent-child call_start records."""

        @weave.op
        def inner(x: int) -> int:
            return x * 2

        @weave.op
        def outer(x: int) -> int:
            return inner(x)

        outer(5)
        wal_client._flush()

        records = _read_all_wal_records(wal_client)

        call_starts = [r for r in records if r["type"] == "call_start"]
        call_ends = [r for r in records if r["type"] == "call_end"]
        assert len(call_starts) == 2
        assert len(call_ends) == 2

        # Find outer and inner by op_name
        outer_start = next(
            s for s in call_starts if "outer" in s["req"]["start"]["op_name"]
        )
        inner_start = next(
            s for s in call_starts if "inner" in s["req"]["start"]["op_name"]
        )

        # Inner call's parent_id should match outer call's id
        assert (
            inner_start["req"]["start"]["parent_id"]
            == outer_start["req"]["start"]["id"]
        )
        # Both should share the same trace_id
        assert (
            inner_start["req"]["start"]["trace_id"]
            == outer_start["req"]["start"]["trace_id"]
        )

        # Verify outputs
        outer_end = next(
            e
            for e in call_ends
            if e["req"]["end"]["id"] == outer_start["req"]["start"]["id"]
        )
        inner_end = next(
            e
            for e in call_ends
            if e["req"]["end"]["id"] == inner_start["req"]["start"]["id"]
        )
        assert inner_end["req"]["end"]["output"] == 10
        assert outer_end["req"]["end"]["output"] == 10

    def test_wal_records_are_json_serializable(self, wal_client):
        """Ensure WAL records round-trip through JSON without loss."""
        weave.publish({"nested": {"list": [1, 2, 3]}}, name="json_obj")
        wal_client._flush()

        records = _read_all_wal_records(wal_client)
        assert len(records) == 1
        roundtripped = json.loads(json.dumps(records[0]))
        assert roundtripped == records[0]

    def test_flush_fsyncs_wal(self, wal_client):
        """flush() should fsync the WAL so records survive a process crash."""
        weave.publish({"a": 1}, name="fsync_obj")
        wal_client.flush()

        records = _read_all_wal_records(wal_client)
        assert len(records) == 1
        assert records[0]["type"] == "obj_create"


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
        weave.publish({"k": "v"}, name="sender_obj")
        wal_client_with_sender._flush()
        wal_dir = Path(wal_client_with_sender._wal.wal_dir)
        wal_client_with_sender._wal.close()

        remaining = list(wal_dir.glob("*.jsonl"))
        assert len(remaining) == 0

    def test_sender_drains_table_create(self, wal_client_with_sender):
        """Table-create records should be drained and files cleaned up."""
        ds = weave.Dataset(name="sender_ds", rows=[{"x": 1}])
        weave.publish(ds, name="sender_ds")
        wal_client_with_sender._flush()
        wal_dir = Path(wal_client_with_sender._wal.wal_dir)
        wal_client_with_sender._wal.close()

        remaining = list(wal_dir.glob("*.jsonl"))
        assert len(remaining) == 0


class TestWALManagerLifecycle:
    """Unit tests for WALManager without a full client."""

    def test_write_only_manager(self, tmp_path):
        """WALManager without sender writes records but doesn't drain them."""
        mgr = WALManager("test-entity", "test-project")
        mgr.wal_dir = str(tmp_path)
        dir_mgr = FileWALDirectoryManager(str(tmp_path))
        mgr._writer = JSONLWALWriter(dir_mgr)

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

        records: list[dict] = []
        for path in sorted(tmp_path.glob("*.jsonl")):
            consumer = JSONLWALConsumer(str(path))
            try:
                for entry in consumer.read_pending():
                    records.append(entry.record)
            finally:
                consumer.close()

        assert len(records) == 1
        assert records[0] == {
            "type": "obj_create",
            "req": {
                "obj": {
                    "project_id": "test-entity/test-project",
                    "object_id": "test_obj",
                    "val": {"hello": "world"},
                    "builtin_object_class": None,
                    "expected_digest": None,
                    "wb_user_id": None,
                }
            },
        }

        # No sender — file should still be on disk.
        assert len(list(tmp_path.glob("*.jsonl"))) == 1
        mgr.close()

    def test_close_is_idempotent(self, tmp_path):
        """Calling close() multiple times should not raise."""
        mgr = WALManager("test-entity", "test-project")
        mgr.close()
        mgr.close()  # second call should be a no-op

    def test_close_with_sender_is_idempotent(self, wal_client_with_sender):
        """close() on a manager with sender should be safe to call twice."""
        wal_client_with_sender._wal.close()
        wal_client_with_sender._wal.close()  # should not raise


class TestTraceServerHandlers:
    """Verify TraceServerHandlers and build_trace_server_handlers."""

    def test_builds_handler_for_every_record_type(self):
        """Should produce a handler for each type in _RECORD_TYPE_TO_REQ."""
        mock_server = MagicMock()
        h = TraceServerHandlers(mock_server)
        handlers = h.as_dict()

        assert set(handlers.keys()) == set(_RECORD_TYPE_TO_REQ.keys())

    def test_handler_calls_correct_server_method(self):
        """Each handler should call the matching method on the server."""
        mock_server = MagicMock()
        handlers = TraceServerHandlers(mock_server).as_dict()

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
        handlers = TraceServerHandlers(mock_server).as_dict()

        req = tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id="e/p",
                rows=[{"val": {"x": 1}, "digest": "abc123"}],
            )
        )
        record = {"type": "table_create", "req": req.model_dump(mode="json")}
        handlers["table_create"](record)

        mock_server.table_create.assert_called_once()

    def test_convenience_function_matches_class(self):
        """build_trace_server_handlers should return the same keys as the class."""
        mock_server = MagicMock()
        from_func = build_trace_server_handlers(mock_server)
        from_class = TraceServerHandlers(mock_server).as_dict()

        assert set(from_func.keys()) == set(from_class.keys())


class TestCreateSender:
    """Verify the create_sender factory wires things up correctly."""

    def test_returns_configured_sender(self, tmp_path):
        """create_sender should return a BackgroundWALSender ready to start."""
        mock_server = MagicMock()
        sender = create_sender(str(tmp_path), mock_server, poll_interval=0.5)

        assert isinstance(sender, BackgroundWALSender)
        assert sender._poll_interval == 0.5

    def test_sender_can_start_and_stop(self, tmp_path):
        """The created sender should be startable and stoppable."""
        mock_server = MagicMock()
        sender = create_sender(str(tmp_path), mock_server, poll_interval=0.1)
        sender.start()
        sender.stop()
