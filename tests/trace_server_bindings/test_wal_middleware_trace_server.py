import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.wal_middleware_trace_server import (
    WriteAheadLogMiddlewareTraceServer,
)


class _FakeWriteServer:
    def __init__(self) -> None:
        self.raise_obj_create = False

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        if self.raise_obj_create:
            raise RuntimeError("network down")
        return tsi.ObjCreateRes(digest="obj-digest", object_id=req.obj.object_id)

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        row_digests = [f"row-{i}" for i, _ in enumerate(req.table.rows)]
        return tsi.TableCreateRes(digest="table-digest", row_digests=row_digests)

    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes:
        return tsi.TableCreateFromDigestsRes(
            digest=_compute_table_digest(req.row_digests)
        )

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        return tsi.FileCreateRes(digest=f"file-{len(req.content)}")


def _read_wal_events(db_path: Path) -> list[tuple]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            """
            SELECT event_type, project_id, status, error_count, last_error, payload_json
            FROM wal_events
            ORDER BY created_at
            """
        ).fetchall()


def _compute_table_digest(row_digests: list[str]) -> str:
    table_hasher = hashlib.sha256()
    for row_digest in row_digests:
        table_hasher.update(row_digest.encode())
    return table_hasher.hexdigest()


def test_obj_create_appends_and_acks_wal_event(tmp_path: Path) -> None:
    wal_db_path = tmp_path / "weave-wal.sqlite3"
    server = WriteAheadLogMiddlewareTraceServer(_FakeWriteServer(), wal_db_path)
    req = tsi.ObjCreateReq(
        obj=tsi.ObjSchemaForInsert(
            project_id="entity/project",
            object_id="my_obj",
            val={"a": 1},
        )
    )

    res = server.obj_create(req)
    assert res.digest == "obj-digest"

    rows = _read_wal_events(wal_db_path)
    assert len(rows) == 1
    event_type, project_id, status, error_count, last_error, payload_json = rows[0]
    assert event_type == "obj_create"
    assert project_id == "entity/project"
    assert status == "acked"
    assert error_count == 0
    assert last_error is None
    payload = json.loads(payload_json)
    assert payload["obj"]["object_id"] == "my_obj"


def test_obj_create_failure_keeps_pending_event(tmp_path: Path) -> None:
    wal_db_path = tmp_path / "weave-wal.sqlite3"
    next_server = _FakeWriteServer()
    next_server.raise_obj_create = True
    server = WriteAheadLogMiddlewareTraceServer(next_server, wal_db_path)
    req = tsi.ObjCreateReq(
        obj=tsi.ObjSchemaForInsert(
            project_id="entity/project",
            object_id="broken_obj",
            val={"a": 1},
        )
    )

    with pytest.raises(RuntimeError, match="network down"):
        server.obj_create(req)

    rows = _read_wal_events(wal_db_path)
    assert len(rows) == 1
    event_type, _, status, error_count, last_error, _ = rows[0]
    assert event_type == "obj_create"
    assert status == "pending"
    assert error_count == 1
    assert "RuntimeError: network down" in last_error


def test_table_create_from_digests_appends_and_acks_wal_event(tmp_path: Path) -> None:
    wal_db_path = tmp_path / "weave-wal.sqlite3"
    server = WriteAheadLogMiddlewareTraceServer(_FakeWriteServer(), wal_db_path)
    req = tsi.TableCreateFromDigestsReq(
        project_id="entity/project",
        row_digests=["row-a", "row-b", "row-c"],
    )

    res = server.table_create_from_digests(req)
    assert res.digest == _compute_table_digest(req.row_digests)

    rows = _read_wal_events(wal_db_path)
    assert len(rows) == 1
    event_type, project_id, status, _, _, payload_json = rows[0]
    assert event_type == "table_create_from_digests"
    assert project_id == "entity/project"
    assert status == "acked"
    payload = json.loads(payload_json)
    assert payload["digest"] == _compute_table_digest(req.row_digests)


def test_table_create_appends_and_acks_wal_event(tmp_path: Path) -> None:
    wal_db_path = tmp_path / "weave-wal.sqlite3"
    server = WriteAheadLogMiddlewareTraceServer(_FakeWriteServer(), wal_db_path)
    req = tsi.TableCreateReq(
        table=tsi.TableSchemaForInsert(
            project_id="entity/project",
            rows=[{"a": 1}, {"a": 2}],
        )
    )

    res = server.table_create(req)
    assert res.digest == "table-digest"

    rows = _read_wal_events(wal_db_path)
    assert len(rows) == 1
    event_type, project_id, status, _, _, payload_json = rows[0]
    assert event_type == "table_create"
    assert project_id == "entity/project"
    assert status == "acked"
    payload = json.loads(payload_json)
    assert payload["table"]["rows"] == [{"a": 1}, {"a": 2}]


def test_file_create_appends_and_acks_wal_event(tmp_path: Path) -> None:
    wal_db_path = tmp_path / "weave-wal.sqlite3"
    server = WriteAheadLogMiddlewareTraceServer(_FakeWriteServer(), wal_db_path)
    req = tsi.FileCreateReq(
        project_id="entity/project",
        name="obj.py",
        content=b"print('hello')",
    )

    res = server.file_create(req)
    assert res.digest == f"file-{len(req.content)}"

    rows = _read_wal_events(wal_db_path)
    assert len(rows) == 1
    event_type, project_id, status, _, _, payload_json = rows[0]
    assert event_type == "file_create"
    assert project_id == "entity/project"
    assert status == "acked"
    payload = json.loads(payload_json)
    assert payload["name"] == "obj.py"
