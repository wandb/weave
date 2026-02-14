"""Tests for ClickHouse batching behavior in the trace server.

This module verifies that multiple calls are properly batched into a single
ClickHouse insert operation for performance optimization.
"""

import base64
import datetime
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.trace.util import client_is_sqlite
from weave.shared.trace_server_interface_util import str_digest
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.base64_content_conversion import AUTO_CONVERSION_MIN_SIZE
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.errors import InvalidRequest, ObjectDeletedError


def make_base_64_content(content: str) -> str:
    """Helper function to create base64 encoded content.

    Args:
        content (str): The content to encode.

    Returns:
        str: Base64 encoded content with data URI prefix.
    """
    return "data:text/plain;base64," + base64.b64encode(content.encode()).decode()


string_suffix = "a" * AUTO_CONVERSION_MIN_SIZE


def test_clickhouse_batching():
    """Test that batched calls are properly sent to ClickHouse with correct parameters."""
    # Create a mock ClickHouse client
    mock_ch_client = MagicMock()

    # Mock the command method to avoid actual database operations
    mock_ch_client.command.return_value = None

    # Mock the insert method to track calls
    mock_ch_client.insert.return_value = MagicMock()
    # MagicMock is truthy, so get_project_data_residence() returns BOTH, which is incorrect, mock it
    mock_ch_client.query.return_value.result_rows = []

    # Create a ClickHouseTraceServer instance and patch _mint_client
    with patch.object(
        ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        trace_server = ClickHouseTraceServer(host="test_host")

        # Use properly base64 encoded project_id (entity/project format)
        project_id = base64.b64encode(b"test_entity/test_project").decode("utf-8")

        # Simulate a legacy project by returning merged-only residence.
        mock_query_result = MagicMock()
        mock_query_result.result_rows = [[0, 1]]  # has_complete=0, has_merged=1
        mock_ch_client.query.return_value = mock_query_result

        # Create a batch of call start requests
        batch_req = tsi.CallCreateBatchReq(
            batch=[
                tsi.CallBatchStartMode(
                    mode="start",
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=project_id,
                            op_name="test_op_1",
                            started_at=datetime.datetime.now(datetime.timezone.utc),
                            attributes={},
                            inputs={
                                "input": make_base_64_content(
                                    "SOME BASE64 CONTENT - 1" + string_suffix
                                )
                            },
                        )
                    ),
                ),
                tsi.CallBatchStartMode(
                    mode="start",
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=project_id,
                            op_name="test_op_2",
                            started_at=datetime.datetime.now(datetime.timezone.utc),
                            attributes={},
                            inputs={
                                "input": make_base_64_content(
                                    "SOME BASE64 CONTENT - 2" + string_suffix
                                )
                            },
                        )
                    ),
                ),
                tsi.CallBatchStartMode(
                    mode="start",
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=project_id,
                            op_name="test_op_3",
                            started_at=datetime.datetime.now(datetime.timezone.utc),
                            attributes={},
                            inputs={
                                "input": make_base_64_content(
                                    "SOME BASE64 CONTENT - 3" + string_suffix
                                )
                            },
                        )
                    ),
                ),
            ]
        )

        # Execute the batch
        trace_server.call_start_batch(batch_req)

        # THE KEY ASSERTION:
        # Verify that there are exactly 2 inserts:
        # 1 for files and 1 for call_parts (order may vary)
        insert_call_count = mock_ch_client.insert.call_count
        assert insert_call_count == 2, (
            f"Expected exactly 2 ClickHouse insert calls for 3 batched calls "
            f"(and 3 base64 content objects, which are stored in files), "
            f"but got {insert_call_count} insert calls"
        )

        # Check that both files and call_parts were inserted (order may vary)
        insert_tables = [
            mock_ch_client.insert.call_args_list[0][0][0],
            mock_ch_client.insert.call_args_list[1][0][0],
        ]
        assert set(insert_tables) == {"files", "call_parts"}, (
            f"Expected inserts to files and call_parts tables, "
            f"but got inserts to: {insert_tables}"
        )


def _mk_obj(project_id: str, object_id: str, wb_user_id: str, val: dict[str, Any]):
    return tsi.ObjSchemaForInsert(
        project_id=project_id,
        object_id=object_id,
        wb_user_id=wb_user_id,
        val=val,
    )


def _internal_pid() -> str:
    # Any base64 string is valid for internal project id validation
    # Reuse the same value as other tests in this module
    return base64.b64encode(b"test_project").decode()


def _internal_wb_user_id() -> str:
    return base64.b64encode(b"test_user").decode()


def test_obj_batch_same_object_id_different_hash(trace_server, client):
    """Two versions for same object_id with different digests."""
    if client_is_sqlite(client):
        pytest.skip("SQLite does not support batch object creation")
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    wb_user_id = _internal_wb_user_id()
    obj_id = "my_obj"
    v1 = {"k": 1}
    v2 = {"k": 2}

    server.obj_create_batch(
        batch=[
            _mk_obj(pid, obj_id, wb_user_id, v1),
            _mk_obj(pid, obj_id, wb_user_id, v2),
        ]
    )

    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    assert len(res.objs) == 2
    digests = {o.digest for o in res.objs}
    assert digests == {str_digest(json.dumps(v1)), str_digest(json.dumps(v2))}
    # Exactly one latest
    assert sum(o.is_latest for o in res.objs) == 1


def test_obj_batch_same_hash_different_object_ids(trace_server, client):
    """Same digest payload uploaded under different object_ids yields distinct objects."""
    if client_is_sqlite(client):
        pytest.skip("SQLite does not support batch object creation")
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    wb_user_id = _internal_wb_user_id()
    val = {"shared": True}
    server.obj_create_batch(
        batch=[
            _mk_obj(pid, "obj_1", wb_user_id, val),
            _mk_obj(pid, "obj_2", wb_user_id, val),
        ]
    )
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(
                object_ids=["obj_1", "obj_2"], latest_only=False
            ),
        )
    )
    assert len(res.objs) == 2
    assert {o.object_id for o in res.objs} == {"obj_1", "obj_2"}


def test_obj_batch_identical_same_id_same_hash_deduplicates(trace_server, client):
    """Duplicate rows (same object_id and digest) are represented once in metadata view."""
    server = trace_server._internal_trace_server
    if client_is_sqlite(client):
        pytest.skip("SQLite does not support batch object creation")
    pid = _internal_pid()
    wb_user_id = _internal_wb_user_id()
    obj_id = "dup_obj"
    val = {"x": 1}
    server.obj_create_batch(
        batch=[
            _mk_obj(pid, obj_id, wb_user_id, val),
            _mk_obj(pid, obj_id, wb_user_id, val),
        ]
    )
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].digest == str_digest(json.dumps(val))


def test_obj_batch_four_versions_and_read_path(trace_server, client):
    """Batch upload 4 versions and verify reads over all and latest work."""
    if client_is_sqlite(client):
        pytest.skip("SQLite does not support batch object creation")
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    wb_user_id = _internal_wb_user_id()
    obj_id = "multi_v"
    vals = [{"i": i} for i in range(4)]
    digests = [str_digest(json.dumps(v)) for v in vals]
    server.obj_create_batch(batch=[_mk_obj(pid, obj_id, wb_user_id, v) for v in vals])

    # All versions are queryable
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    assert len(res.objs) == 4
    assert {o.digest for o in res.objs} == set(digests)
    assert sum(o.is_latest for o in res.objs) == 1

    # Each digest can be read specifically
    for d, v in zip(digests, vals, strict=False):
        read = server.obj_read(
            tsi.ObjReadReq(project_id=pid, object_id=obj_id, digest=d)
        )
        assert read.obj.val == v

    # Latest alias reads the most recent version
    latest = server.obj_read(
        tsi.ObjReadReq(project_id=pid, object_id=obj_id, digest="latest")
    )
    assert latest.obj.digest in set(digests)
    assert latest.obj.is_latest == 1


def test_obj_batch_delete_version_preserves_indices(trace_server, client):
    """Delete one version and ensure indices remain intact and deletion is reflected."""
    if client_is_sqlite(client):
        pytest.skip("SQLite does not support batch object creation")
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    wb_user_id = _internal_wb_user_id()
    obj_id = "del_v"
    vals = [{"i": i} for i in range(3)]
    delete_idx = 1

    server.obj_create_batch(batch=[_mk_obj(pid, obj_id, wb_user_id, v) for v in vals])
    # Remaining versions are intact; indices are not renumbered in metadata
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    pre_del_digests = [obj.digest for obj in res.objs]

    # Delete the middle version
    del_digest = pre_del_digests[delete_idx]

    server.obj_delete(
        tsi.ObjDeleteReq(project_id=pid, object_id=obj_id, digests=[del_digest])
    )

    # Reading deleted digest raises ObjectDeletedError
    with pytest.raises(ObjectDeletedError):
        server.obj_read(
            tsi.ObjReadReq(project_id=pid, object_id=obj_id, digest=del_digest)
        )

    # Remaining versions are intact; indices are not renumbered in metadata
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    assert len(res.objs) == 2
    assert {obj.digest for obj in res.objs} == {pre_del_digests[0], pre_del_digests[2]}


def test_obj_batch_mixed_projects_errors(trace_server, client):
    """Uploading objects to different projects in one batch should error."""
    if client_is_sqlite(client):
        pytest.skip("SQLite does not support batch object creation")
    server = trace_server._internal_trace_server
    pid1 = _internal_pid()
    wb_user_id = _internal_wb_user_id()
    pid2 = "cHJvamVjdF8y"  # base64("project_2")
    batch = [
        _mk_obj(pid1, "p1_obj", wb_user_id, {"a": 1}),
        _mk_obj(pid2, "p2_obj", wb_user_id, {"b": 2}),
    ]

    with pytest.raises(
        InvalidRequest,
        match="obj_create_batch only supports updating a single project.",
    ):
        server.obj_create_batch(batch=batch)
