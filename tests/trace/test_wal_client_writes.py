"""Tests for the WAL (Write-Ahead Log) feature.

Covers:
- Client writes to WAL when enabled
- Client works normally when WAL is disabled (default)
- WALManager lifecycle (write-only and with sender)
- TraceServerHandlers and create_sender
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

import weave
from weave.durability.wal_client_id import compute_client_id
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
from weave.trace import weave_client
from weave.trace.settings import UserSettings, override_settings
from weave.trace_server import trace_server_interface as tsi

# The initial WAL points at the shared ~/.weave/wal/<entity>/<project>/
# directory, so starting a sender there races with parallel xdist workers
# and has triggered Windows file-handle errors.  Both fixtures redirect
# to an isolated tmp_path, so no sender needs to run against the default.
_INITIAL_WAL_SETTINGS = UserSettings(enable_wal=True, disable_wal_sender=True)


@pytest.fixture
def wal_client(client_creator, tmp_path):
    """Create a client with WAL enabled but sender stopped (write-only)."""
    wal_dir = str(tmp_path / "wal")
    with client_creator(settings=_INITIAL_WAL_SETTINGS) as client:
        _redirect_wal_to(client, wal_dir)
        yield client


@pytest.fixture
def wal_client_with_sender(client_creator, tmp_path):
    """Create a client with WAL enabled and sender running."""
    wal_dir = str(tmp_path / "wal")
    with client_creator(settings=_INITIAL_WAL_SETTINGS) as client:
        _redirect_wal_to(client, wal_dir)
        client._wal._sender = create_sender(wal_dir, client.server)
        client._wal._sender.start()
        yield client


def test_obj_table_and_file_create_write_records(wal_client):
    """obj_create, table_create, and image publish (file+obj) all hit the WAL."""
    project_id = f"{wal_client.entity}/{wal_client.project}"

    weave.publish({"model": "gpt-4", "temp": 0.7}, name="my_obj")
    wal_client._flush()
    records = _read_all_wal_records(wal_client)
    assert len(records) == 1
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

    wal_client._send_table_create([{"x": 1}, {"x": 2}])
    wal_client._flush()
    table_recs = [r for r in _read_all_wal_records(wal_client) if r["type"] == "table_create"]
    assert len(table_recs) == 1
    assert table_recs[0] == {
        "type": "table_create",
        "req": {
            "table": {
                "project_id": project_id,
                "rows": [{"x": 1}, {"x": 2}],
                "expected_digest": None,
            }
        },
    }

    img = Image.new("RGB", (2, 2), color="red")
    weave.publish(img, name="my_image")
    wal_client._flush()
    img_records = _read_all_wal_records(wal_client)
    file_recs = [r for r in img_records if r["type"] == "file_create"]
    assert any(
        r["req"]["project_id"] == project_id and r["req"]["name"] == "obj.py"
        for r in file_recs
    )
    image_obj = next(
        r
        for r in img_records
        if r["type"] == "obj_create"
        and r["req"]["obj"]["object_id"] == "my_image"
    )
    assert image_obj["req"]["obj"]["val"]["weave_type"] == {"type": "PIL.Image.Image"}


def test_call_start_and_end_records(wal_client):
    """A traced op writes one call_start and one call_end with all fields populated."""

    @weave.op
    def add(a: int, b: int) -> int:
        return a + b

    add(1, 2)
    wal_client._flush()

    records = _read_all_wal_records(wal_client)
    project_id = f"{wal_client.entity}/{wal_client.project}"

    call_starts = [r for r in records if r["type"] == "call_start"]
    call_ends = [r for r in records if r["type"] == "call_end"]
    assert len(call_starts) == 1
    assert len(call_ends) == 1

    start = call_starts[0]["req"]["start"]
    assert start["project_id"] == project_id
    assert "/op/add:" in start["op_name"]
    assert start["inputs"] == {"a": 1, "b": 2}
    assert start["id"] is not None
    assert start["trace_id"] is not None
    assert start["started_at"] is not None
    assert isinstance(start["attributes"], dict)
    assert start["parent_id"] is None

    end = call_ends[0]["req"]["end"]
    assert end["project_id"] == project_id
    assert end["id"] is not None
    assert end["output"] == 3
    assert end["ended_at"] is not None
    assert end["exception"] is None
    assert isinstance(end["summary"], dict)


def test_call_with_exception(wal_client):
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


def test_nested_calls(wal_client):
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

    outer_start = next(s for s in call_starts if "outer" in s["req"]["start"]["op_name"])
    inner_start = next(s for s in call_starts if "inner" in s["req"]["start"]["op_name"])
    assert (
        inner_start["req"]["start"]["parent_id"] == outer_start["req"]["start"]["id"]
    )
    assert (
        inner_start["req"]["start"]["trace_id"]
        == outer_start["req"]["start"]["trace_id"]
    )

    outer_end = next(
        e for e in call_ends if e["req"]["end"]["id"] == outer_start["req"]["start"]["id"]
    )
    inner_end = next(
        e for e in call_ends if e["req"]["end"]["id"] == inner_start["req"]["start"]["id"]
    )
    assert inner_end["req"]["end"]["output"] == 10
    assert outer_end["req"]["end"]["output"] == 10


def test_wal_records_json_serializable_and_flush_fsyncs(wal_client):
    """Records round-trip through JSON, and flush() fsyncs (records survive a crash)."""
    weave.publish({"nested": {"list": [1, 2, 3]}}, name="json_obj")
    wal_client._flush()
    records = _read_all_wal_records(wal_client)
    assert len(records) == 1
    assert json.loads(json.dumps(records[0])) == records[0]

    weave.publish({"a": 1}, name="fsync_obj")
    wal_client.flush()
    records = _read_all_wal_records(wal_client)
    fsync_recs = [r for r in records if r["req"]["obj"]["object_id"] == "fsync_obj"]
    assert len(fsync_recs) == 1
    assert fsync_recs[0]["type"] == "obj_create"


def test_client_works_when_wal_disabled(client, weave_active):
    """Default client has _wal=None; publish/dataset-publish/flush all work."""
    assert client._wal is None

    assert weave.publish({"key": "value"}, name="no_wal_obj") is not None
    ds = weave.Dataset(name="no_wal_ds", rows=[{"x": 1}])
    assert weave.publish(ds, name="no_wal_ds") is not None

    weave.publish({"a": 1}, name="flush_obj")
    client.flush()  # must not raise


@pytest.mark.parametrize("publish_fn", ["obj", "dataset"])
def test_sender_drains_wal_on_close(wal_client_with_sender, publish_fn):
    """The in-process sender drains obj and table records, leaving no files on close."""
    if publish_fn == "obj":
        weave.publish({"k": "v"}, name="sender_obj")
    else:
        weave.publish(weave.Dataset(name="sender_ds", rows=[{"x": 1}]), name="sender_ds")
    wal_client_with_sender._flush()
    wal_dir = Path(wal_client_with_sender._wal.wal_dir)
    wal_client_with_sender._wal.close()
    assert len(list(wal_dir.glob("*.jsonl"))) == 0


def test_write_only_manager_persists_records(tmp_path):
    """WALManager without sender writes records but doesn't drain them."""
    mgr = WALManager("test-entity", "test-project")
    mgr.wal_dir = str(tmp_path)
    mgr._writer = JSONLWALWriter(FileWALDirectoryManager(str(tmp_path)))

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


@pytest.mark.disable_logging_error_check
def test_close_is_idempotent(tmp_path, wal_client_with_sender):
    """close() is safe to call twice, both bare-manager and with a running sender."""
    mgr = WALManager("test-entity", "test-project")
    mgr.close()
    mgr.close()

    wal_client_with_sender._wal.close()
    wal_client_with_sender._wal.close()


def test_trace_server_handlers_dispatch():
    """Handlers cover every record type and each replays the dict to the matching method.

    Covers the obj_create, table_create, and call_start replay paths plus parity
    between the class `as_dict()` and the `build_trace_server_handlers` convenience.
    """
    mock_server = MagicMock()
    handlers = TraceServerHandlers(mock_server).as_dict()
    assert set(handlers.keys()) == set(_RECORD_TYPE_TO_REQ.keys())
    assert set(build_trace_server_handlers(mock_server).keys()) == set(handlers.keys())

    obj_req = tsi.ObjCreateReq(
        obj=tsi.ObjSchemaForInsert(project_id="e/p", object_id="test", val={"x": 1})
    )
    handlers["obj_create"]({"type": "obj_create", "req": obj_req.model_dump(mode="json")})
    mock_server.obj_create.assert_called_once()
    obj_arg = mock_server.obj_create.call_args[0][0]
    assert isinstance(obj_arg, tsi.ObjCreateReq)
    assert obj_arg.obj.object_id == "test"

    table_req = tsi.TableCreateReq(
        table=tsi.TableSchemaForInsert(
            project_id="e/p", rows=[{"val": {"x": 1}, "digest": "abc123"}]
        )
    )
    handlers["table_create"](
        {"type": "table_create", "req": table_req.model_dump(mode="json")}
    )
    mock_server.table_create.assert_called_once()

    started = datetime.datetime.now(datetime.timezone.utc)
    start_req = tsi.CallStartReq(
        start=tsi.StartedCallSchemaForInsert(
            project_id="e/p",
            op_name="predict",
            trace_id="t1",
            started_at=started,
            attributes={"k": "v"},
            inputs={"x": 1},
        )
    )
    handlers["call_start"](
        {"type": "call_start", "req": start_req.model_dump(mode="json")}
    )
    mock_server.call_start.assert_called_once()
    start_arg = mock_server.call_start.call_args[0][0]
    assert isinstance(start_arg, tsi.CallStartReq)
    assert start_arg.start.op_name == "predict"
    assert start_arg.start.started_at == started
    assert start_arg.start.attributes == {"k": "v"}
    assert start_arg.start.inputs == {"x": 1}


def test_file_create_roundtrips_bytes_content():
    """file_create handler must preserve bytes content through replay.

    Pydantic v2 dumps bytes fields as utf-8 strings under mode="json" and
    model_validate re-encodes them; the round-trip must be lossless for content
    that actually reaches the WAL (non-utf8 bytes fail at write time).
    """
    mock_server = MagicMock()
    handlers = TraceServerHandlers(mock_server).as_dict()

    original_content = "small file body — including non-ascii: café 🎉".encode()
    req = tsi.FileCreateReq(project_id="e/p", name="note.txt", content=original_content)
    handlers["file_create"]({"type": "file_create", "req": req.model_dump(mode="json")})

    mock_server.file_create.assert_called_once()
    call_arg = mock_server.file_create.call_args[0][0]
    assert isinstance(call_arg, tsi.FileCreateReq)
    assert call_arg.content == original_content


def test_create_sender_returns_startable_sender(tmp_path):
    """create_sender returns a configured BackgroundWALSender that starts and stops."""
    mock_server = MagicMock()
    sender = create_sender(str(tmp_path), mock_server, poll_interval=0.5)
    assert isinstance(sender, BackgroundWALSender)
    assert sender._poll_interval == 0.5

    sender2 = create_sender(str(tmp_path), mock_server, poll_interval=0.1)
    sender2.start()
    sender2.stop()


@pytest.mark.parametrize("with_api_key", [True, False])
def test_wal_directory_namespacing_by_api_key(client, with_api_key):
    """With api_key the WAL dir ends in an HMAC subdir; without it, the flat project path."""
    api_key = "wk-test-key-for-wal-namespacing" if with_api_key else None
    with override_settings(enable_wal=True, disable_wal_sender=True):
        wc = weave_client.WeaveClient(
            client.entity,
            client.project,
            client.server,
            ensure_project_exists=False,
            api_key=api_key,
        )
        try:
            assert wc._wal is not None
            if with_api_key:
                assert wc._wal.wal_dir.endswith(compute_client_id(api_key))
            else:
                assert wc._wal.wal_dir.endswith(wc.project)
        finally:
            wc._wal.close()


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
    """Replace the client's WAL writer to use *wal_dir* for test isolation."""
    wal = client._wal
    wal.close()
    wal.wal_dir = wal_dir
    wal._writer = JSONLWALWriter(FileWALDirectoryManager(wal_dir))
