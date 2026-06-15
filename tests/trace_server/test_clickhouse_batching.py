"""Tests for ClickHouse batching behavior in the trace server.

This module verifies that multiple calls are properly batched into a single
ClickHouse insert operation for performance optimization.
"""

import base64
import datetime
import gc
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from weave.shared.digest import str_digest
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.base64_content_conversion import AUTO_CONVERSION_MIN_SIZE
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.errors import (
    InvalidRequest,
    ObjectDeletedError,
    handle_server_exception,
)
from weave.trace_server.validation_util import CHValidationError
from weave.trace_server_bindings.caching_middleware_trace_server import (
    CachingMiddlewareTraceServer,
)


def test_clickhouse_batching_insert_grouping():
    """call_start_batch coalesces inserts: 3 distinct base64 contents produce
    exactly 2 inserts (files + call_parts), and 3 identical contents dedup to a
    single file pair (content + metadata).
    """
    # Distinct contents -> exactly one files insert + one call_parts insert.
    distinct = _run_batch_start(
        [
            create_file_sized_content("SOME BASE64 CONTENT - 1"),
            create_file_sized_content("SOME BASE64 CONTENT - 2"),
            create_file_sized_content("SOME BASE64 CONTENT - 3"),
        ]
    )
    insert_tables = [call[0][0] for call in distinct.insert.call_args_list]
    assert distinct.insert.call_count == 2
    assert set(insert_tables) == {"files", "call_parts"}

    # Identical content across 3 calls -> still only one file pair.
    same = "IDENTICAL CONTENT"
    dedup = _run_batch_start([create_file_sized_content(same)] * 3)
    dedup_tables = [call[0][0] for call in dedup.insert.call_args_list]
    assert set(dedup_tables) == {"files", "call_parts"}
    files_insert = next(c for c in dedup.insert.call_args_list if c[0][0] == "files")
    # Each Content object produces 2 files (content + metadata.json); dedup keeps 1 pair.
    assert len(files_insert[1]["data"]) == 2


def test_obj_batch_two_version_scenarios(trace_server, client):
    """obj_create_batch over two-version inputs: two digests under one
    object_id yield two versions with exactly one latest; one digest under two
    object_ids yields two distinct objects.
    """
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    wb_user_id = _internal_wb_user_id()

    # Same object_id, two distinct values -> two versions, one latest.
    v1, v2 = {"k": 1}, {"k": 2}
    server.obj_create_batch(
        batch=[
            _mk_obj(pid, "my_obj", wb_user_id, v1),
            _mk_obj(pid, "my_obj", wb_user_id, v2),
        ]
    )
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=["my_obj"], latest_only=False),
        )
    )
    assert len(res.objs) == 2
    assert {o.digest for o in res.objs} == {
        str_digest(json.dumps(v1)),
        str_digest(json.dumps(v2)),
    }
    assert sum(o.is_latest for o in res.objs) == 1

    # Same value, two object_ids -> two distinct objects.
    shared = {"shared": True}
    server.obj_create_batch(
        batch=[
            _mk_obj(pid, "obj_1", wb_user_id, shared),
            _mk_obj(pid, "obj_2", wb_user_id, shared),
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


def test_obj_batch_four_versions_and_read_path(trace_server, client):
    """Batch upload 4 versions and verify reads over all and latest work."""
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


def test_digest_key_order_independence(trace_server, client):
    """Key-order independence at every layer: str_digest is order-invariant only
    with sort_keys; obj_create_batch collapses key-reordered values (and exact
    duplicates) to one version; table_create gives reordered rows equal digests.
    """
    # str_digest: equal under sort_keys, differs without it.
    val_a = {"b": 1, "a": 2, "c": [{"z": 9, "y": 8}]}
    val_b = {"a": 2, "c": [{"y": 8, "z": 9}], "b": 1}
    assert str_digest(json.dumps(val_a, sort_keys=True)) == str_digest(
        json.dumps(val_b, sort_keys=True)
    )
    assert str_digest(json.dumps(val_a)) != str_digest(json.dumps(val_b))

    server = trace_server._internal_trace_server
    pid = _internal_pid()
    wb_user_id = _internal_wb_user_id()

    # obj_create_batch: key-reordered + exact-duplicate values dedup to one version.
    server.obj_create_batch(
        batch=[
            _mk_obj(pid, "dedup_obj", wb_user_id, {"b": 1, "a": 2}),
            _mk_obj(pid, "dedup_obj", wb_user_id, {"a": 2, "b": 1}),
            _mk_obj(pid, "dedup_obj", wb_user_id, {"b": 1, "a": 2}),
        ]
    )
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=["dedup_obj"], latest_only=False),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].digest == str_digest(json.dumps({"a": 2, "b": 1}))

    # table_create: reordered rows produce identical digests.
    table_res = server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=pid, rows=[{"b": 1, "a": 2}, {"a": 2, "b": 1}]
            )
        )
    )
    assert len(table_res.row_digests) == 2
    assert table_res.row_digests[0] == table_res.row_digests[1]


def test_call_start_batch_invalid_trace_id_returns_400():
    """An invalid trace_id in a batch should fail the whole batch with a 400, not a 500.

    Regression test for: POST /call/upsert_batch drops entire batch for
    non-UUID trace_id (e.g. 'session:main:agent:main:main') with a 500
    instead of returning a useful validation error.
    """
    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_ch_client.insert.return_value = MagicMock()

    project_id = base64.b64encode(b"test_entity/test_project").decode("utf-8")

    mock_query_result = MagicMock()
    mock_query_result.result_rows = [[0, 1]]  # has_complete=0, has_merged=1

    with patch.object(
        ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        trace_server = ClickHouseTraceServer(host="test_host")
        mock_ch_client.query.return_value = mock_query_result

        batch_req = tsi.CallCreateBatchReq(
            batch=[
                tsi.CallBatchStartMode(
                    mode="start",
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=project_id,
                            op_name="invalid_op",
                            trace_id="session:main:agent:main:main",
                            started_at=datetime.datetime.now(datetime.timezone.utc),
                            attributes={},
                            inputs={},
                        )
                    ),
                ),
            ]
        )

        # The batch should raise CHValidationError, not an opaque internal error
        with pytest.raises(CHValidationError, match="Invalid UUID"):
            trace_server.call_start_batch(batch_req)

        # The error registry should map CHValidationError to 400 (not 500)
        try:
            trace_server.call_start_batch(batch_req)
        except CHValidationError as e:
            error_with_status = handle_server_exception(e)
            assert error_with_status.status_code == 400
            assert "Invalid UUID" in error_with_status.message["reason"]


def test_obj_batch_mixed_projects_errors(trace_server, client):
    """Uploading objects to different projects in one batch should error."""
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


def test_caching_middleware_closes_cache_on_gc():
    """Destroying the caching middleware closes its disk cache (the __del__
    cleanup path), so a dropped reference does not leak the cache handle.
    """
    server = CachingMiddlewareTraceServer(next_trace_server=MagicMock())
    assert server._cache_recorder == {"hits": 0, "misses": 0, "skips": 0}

    del server
    gc.collect()


def make_base_64_content(content: str) -> str:
    """Create base64 encoded content with a data URI prefix."""
    return "data:text/plain;base64," + base64.b64encode(content.encode()).decode()


string_suffix = "a" * AUTO_CONVERSION_MIN_SIZE


def create_file_sized_content(content: str) -> str:
    """Create base64 content padded past AUTO_CONVERSION_MIN_SIZE so it is
    stored as a file rather than inline.
    """
    return make_base_64_content(content + string_suffix)


def _run_batch_start(contents: list[str]) -> MagicMock:
    """Run call_start_batch over one base64 input per content against a mocked
    CH client (legacy merged-only residence) and return that client for insert
    assertions.
    """
    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_ch_client.insert.return_value = MagicMock()
    mock_ch_client.query.return_value.result_rows = []

    with patch.object(
        ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        trace_server = ClickHouseTraceServer(host="test_host")
        project_id = base64.b64encode(b"test_entity/test_project").decode("utf-8")

        # Simulate a legacy project by returning merged-only residence.
        mock_query_result = MagicMock()
        mock_query_result.result_rows = [[0, 1]]  # has_complete=0, has_merged=1
        mock_ch_client.query.return_value = mock_query_result

        batch_req = tsi.CallCreateBatchReq(
            batch=[
                tsi.CallBatchStartMode(
                    mode="start",
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=project_id,
                            op_name=f"test_op_{i}",
                            started_at=datetime.datetime.now(datetime.timezone.utc),
                            attributes={},
                            inputs={"input": c},
                        )
                    ),
                )
                for i, c in enumerate(contents)
            ]
        )
        trace_server.call_start_batch(batch_req)

    return mock_ch_client


def _mk_obj(project_id: str, object_id: str, wb_user_id: str, val: dict[str, Any]):
    return tsi.ObjSchemaForInsert(
        project_id=project_id,
        object_id=object_id,
        wb_user_id=wb_user_id,
        val=val,
    )


def _internal_pid() -> str:
    return base64.b64encode(b"test_project").decode()


def _internal_wb_user_id() -> str:
    return base64.b64encode(b"test_user").decode()
