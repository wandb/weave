import hashlib
import json

import pytest

from weave.shared import (
    build_file_create_event,
    build_obj_create_event,
    build_table_create_event,
    compute_file_digest,
    compute_object_digest,
    compute_object_digest_result,
    compute_row_digest,
    compute_table_digest,
)
from weave.shared.object_class_util import process_incoming_object_val
from weave.trace_server.trace_server_interface import (
    FileCreateReq,
    ObjCreateReq,
    ObjSchemaForInsert,
    TableCreateReq,
    TableSchemaForInsert,
)
from weave.shared.trace_server_interface_util import bytes_digest, str_digest

pytestmark = pytest.mark.trace_server


def test_compute_object_digest_matches_server_formula() -> None:
    val = {"a": 1, "nested": {"k": "v"}}
    processed = process_incoming_object_val(val)
    expected = str_digest(json.dumps(processed["val"]))
    assert compute_object_digest(val) == expected


def test_compute_object_digest_result_has_expected_fields() -> None:
    val = {"a": 1}
    result = compute_object_digest_result(val)
    assert result.processed_val == val
    assert result.json_val == json.dumps(val)
    assert result.digest == str_digest(json.dumps(val))
    assert result.base_object_class is None
    assert result.leaf_object_class is None


def test_compute_table_digest_matches_server_formula() -> None:
    rows = [{"x": 1}, {"x": 2}]
    expected_row_digests = [str_digest(json.dumps(r)) for r in rows]
    table_hasher = hashlib.sha256()
    for row_digest in expected_row_digests:
        table_hasher.update(row_digest.encode())
    expected_table_digest = table_hasher.hexdigest()

    assert [compute_row_digest(r) for r in rows] == expected_row_digests
    assert compute_table_digest(expected_row_digests) == expected_table_digest


def test_compute_file_digest_matches_server_formula() -> None:
    content = b"hello-shared"
    assert compute_file_digest(content) == bytes_digest(content)


def test_build_obj_create_event() -> None:
    req = ObjCreateReq(
        obj=ObjSchemaForInsert(
            project_id="entity/project",
            object_id="my_obj",
            val={"a": 1},
        )
    )
    event = build_obj_create_event(req)
    assert event.body.event_type == "obj_create"
    assert event.body.project_id == req.obj.project_id
    assert event.body.object_id == req.obj.object_id
    assert event.body.digest == compute_object_digest(req.obj.val)
    assert event.body.val_json == json.dumps(event.body.processed_val)


def test_build_table_create_event() -> None:
    rows = [{"a": 1}, {"a": 2}, {"a": 3}]
    req = TableCreateReq(
        table=TableSchemaForInsert(project_id="entity/project", rows=rows)
    )
    event = build_table_create_event(req)
    assert event.body.event_type == "table_create"
    assert event.body.project_id == req.table.project_id
    assert event.body.rows == rows
    assert event.body.row_digests == [compute_row_digest(r) for r in rows]
    assert event.body.digest == compute_table_digest(event.body.row_digests)


def test_build_file_create_event() -> None:
    req = FileCreateReq(project_id="entity/project", name="obj.py", content=b"abc123")
    event = build_file_create_event(req)
    assert event.body.event_type == "file_create"
    assert event.body.project_id == req.project_id
    assert event.body.name == req.name
    assert event.body.content == req.content
    assert event.body.digest == compute_file_digest(req.content)
