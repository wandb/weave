"""Tests for ClickHouse batching behavior in the trace server.

This module verifies that multiple calls are properly batched into a single
ClickHouse insert operation for performance optimization.
"""

import base64
import urllib
import pytest
import datetime
from unittest.mock import MagicMock, patch

from tests.trace_server.conftest import TEST_ENTITY
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.base64_content_conversion import AUTO_CONVERSION_MIN_SIZE
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.refs_internal import InvalidInternalRef
from weave.trace_server.errors import ObjectDeletedError


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

    # Create a ClickHouseTraceServer instance and patch _mint_client
    with patch.object(
        ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        trace_server = ClickHouseTraceServer(host="test_host")

        # Use properly base64 encoded project_id (entity/project format)
        project_id = base64.b64encode(b"test_entity/test_project").decode("utf-8")

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


def _to_internal_id(ext: str) -> str:
    return base64.b64encode(ext.encode("utf-8")).decode("utf-8")


def test_save_object_batch(trace_server):
    # Use internal server directly
    internal = trace_server._internal_trace_server
    project_ext = f"{TEST_ENTITY}/obj_batch_save"
    project_id = _to_internal_id(project_ext)
    user_id = _to_internal_id("abc123")

    batch_req = tsi.ObjCreateBatchReq(
        batch=[
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="obj-a",
                val={"a": 1},
                wb_user_id=user_id,
            ),
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="obj-b",
                val={"b": 2},
                wb_user_id=user_id,
            ),
        ]
    )

    create_batch_res = internal.obj_create_batch(batch_req)
    assert len(create_batch_res.results) == 2

    # Read back and verify values match
    for expected_oid, expected_val, res in zip(
        ["obj-a", "obj-b"], [{"a": 1}, {"b": 2}], create_batch_res.results
    ):
        assert res.object_id == expected_oid
        read_res = internal.obj_read(
            tsi.ObjReadReq(
                project_id=project_id,
                object_id=expected_oid,
                digest=res.digest,
            )
        )
        assert read_res.obj.val == expected_val


def test_robust_to_url_sensitive_chars_batch(trace_server):
    internal = trace_server._internal_trace_server
    project_ext = f"{TEST_ENTITY}/obj_batch_url_chars"
    project_id = _to_internal_id(project_ext)
    object_id = "mali_cious-obj.ect"
    bad_key = "mali:cious/ke%y"
    bad_val = {bad_key: "hello world"}
    user_id = _to_internal_id("abc123")

    # Create two objects via batch, one with URL-sensitive chars in keys
    create_batch_res = internal.obj_create_batch(
        tsi.ObjCreateBatchReq(
            batch=[
                tsi.ObjSchemaForInsert(
                    project_id=project_id,
                    object_id=object_id,
                    val=bad_val,
                    wb_user_id=user_id,
                ),
                tsi.ObjSchemaForInsert(
                    project_id=project_id,
                    object_id="normal",
                    val={"x": 1},
                    wb_user_id=user_id,
                ),
            ]
        )
    )

    # Validate read by ref works for the object with special key
    created = create_batch_res.results[0]

    read_res = internal.refs_read_batch(
        tsi.RefsReadBatchReq(
            refs=[
                f"weave:///{project_id}/object/{object_id}:{created.digest}",
            ]
        )
    )
    assert read_res.vals[0] == bad_val

    # Using a non-encoded key in ref path should raise
    with pytest.raises(InvalidInternalRef):
        internal.refs_read_batch(
            tsi.RefsReadBatchReq(
                refs=[
                    f"weave:///{project_id}/object/{object_id}:{created.digest}/key/{bad_key}"
                ]
            )
        )

    encoded_bad_key = urllib.parse.quote_plus(bad_key)
    assert encoded_bad_key == "mali%3Acious%2Fke%25y"
    read_res = internal.refs_read_batch(
        tsi.RefsReadBatchReq(
            refs=[
                f"weave:///{project_id}/object/{object_id}:{created.digest}/key/{encoded_bad_key}",
            ]
        )
    )
    assert read_res.vals[0] == bad_val[bad_key]


def test_batch_upload_same_object_id_different_hash(trace_server):
    """Batch uploading two objects with the same object_id but different hash."""
    internal = trace_server._internal_trace_server
    project_ext = f"{TEST_ENTITY}/obj_batch_diff_hash"
    project_id = _to_internal_id(project_ext)
    user_id = _to_internal_id("abc123")

    batch_req = tsi.ObjCreateBatchReq(
        batch=[
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="same-obj",
                val={"version": 1},
                wb_user_id=user_id,
            ),
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="same-obj",
                val={"version": 2},
                wb_user_id=user_id,
            ),
        ]
    )

    create_batch_res = internal.obj_create_batch(batch_req)
    assert len(create_batch_res.results) == 2

    # Should have different digests since values are different
    digest_1 = create_batch_res.results[0].digest
    digest_2 = create_batch_res.results[1].digest
    assert digest_1 != digest_2

    # Both versions should be readable
    read_res_1 = internal.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="same-obj",
            digest=digest_1,
        )
    )
    assert read_res_1.obj.val == {"version": 1}

    read_res_2 = internal.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="same-obj",
            digest=digest_2,
        )
    )
    assert read_res_2.obj.val == {"version": 2}


def test_batch_upload_same_hash_different_object_id(trace_server):
    """Batch uploading objects with same hash but different object_id."""
    internal = trace_server._internal_trace_server
    project_ext = f"{TEST_ENTITY}/obj_batch_same_hash"
    project_id = _to_internal_id(project_ext)
    same_val = {"data": "identical"}
    user_id = _to_internal_id("abc123")

    batch_req = tsi.ObjCreateBatchReq(
        batch=[
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="obj-1",
                val=same_val,
                wb_user_id=user_id,
            ),
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="obj-2",
                val=same_val,
                wb_user_id=user_id,
            ),
        ]
    )

    create_batch_res = internal.obj_create_batch(batch_req)
    assert len(create_batch_res.results) == 2

    # Should have same digest since values are identical
    digest_1 = create_batch_res.results[0].digest
    digest_2 = create_batch_res.results[1].digest
    assert digest_1 == digest_2

    # Both object_ids should be different
    assert create_batch_res.results[0].object_id == "obj-1"
    assert create_batch_res.results[1].object_id == "obj-2"

    # Both should be readable with their respective object_ids
    read_res_1 = internal.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="obj-1",
            digest=digest_1,
        )
    )
    assert read_res_1.obj.val == same_val

    read_res_2 = internal.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="obj-2",
            digest=digest_2,
        )
    )
    assert read_res_2.obj.val == same_val


def test_batch_upload_identical_object_id_and_hash(trace_server):
    """Batch uploading identical objects (same object_id and hash)."""
    internal = trace_server._internal_trace_server
    project_ext = f"{TEST_ENTITY}/obj_batch_identical"
    project_id = _to_internal_id(project_ext)
    identical_val = {"data": "same"}
    user_id = _to_internal_id("abc123")

    batch_req = tsi.ObjCreateBatchReq(
        batch=[
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="identical-obj",
                val=identical_val,
                wb_user_id=user_id,
            ),
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="identical-obj",
                val=identical_val,
                wb_user_id=user_id,
            ),
        ]
    )

    create_batch_res = internal.obj_create_batch(batch_req)
    assert len(create_batch_res.results) == 2

    # Should have identical results (idempotent)
    digest_1 = create_batch_res.results[0].digest
    digest_2 = create_batch_res.results[1].digest
    assert digest_1 == digest_2
    assert create_batch_res.results[0].object_id == create_batch_res.results[1].object_id

    # Should be readable
    read_res = internal.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="identical-obj",
            digest=digest_1,
        )
    )
    assert read_res.obj.val == identical_val
    obj_query_req = tsi.ObjQueryReq(
        project_id=project_id,
        filter=tsi.ObjectVersionFilter(object_ids=["identical-obj"]),
    )
    # Ensure only one obj was created
    assert len(internal.objs_query(obj_query_req).objs) == 1


def test_batch_upload_multiple_versions_then_read(trace_server):
    """Batch uploading 4 versions of the same object, then confirm read path works."""
    internal = trace_server._internal_trace_server
    project_ext = f"{TEST_ENTITY}/obj_batch_versions"
    project_id = _to_internal_id(project_ext)
    user_id = _to_internal_id("abc123")

    batch_req = tsi.ObjCreateBatchReq(
        batch=[
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="versioned-obj",
                val={"version": i},
                wb_user_id=user_id,
            )
            for i in range(1, 5)
        ]
    )

    create_batch_res = internal.obj_create_batch(batch_req)
    assert len(create_batch_res.results) == 4

    # All digests should be different
    digests = [res.digest for res in create_batch_res.results]
    assert len(set(digests)) == 4, "All versions should have unique digests"

    # All versions should be readable
    for i, digest in enumerate(digests, start=1):
        read_res = internal.obj_read(
            tsi.ObjReadReq(
                project_id=project_id,
                object_id="versioned-obj",
                digest=digest,
            )
        )
        assert read_res.obj.val == {"version": i}


def test_batch_upload_delete_version_with_multiple_versions(trace_server):
    """Deleting an object version for an object with multiple versions after batch uploading."""
    internal = trace_server._internal_trace_server
    project_ext = f"{TEST_ENTITY}/obj_batch_delete"
    project_id = _to_internal_id(project_ext)
    user_id = _to_internal_id("abc123")

    # Create multiple versions via batch
    batch_req = tsi.ObjCreateBatchReq(
        batch=[
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="multi-version-obj",
                val={"version": i},
                wb_user_id=user_id,
            )
            for i in range(1, 5)
        ]
    )

    create_batch_res = internal.obj_create_batch(batch_req)
    assert len(create_batch_res.results) == 4
    digests = [res.digest for res in create_batch_res.results]

    # Delete the first version
    internal.obj_delete(
        tsi.ObjDeleteReq(
            project_id=project_id,
            object_id="multi-version-obj",
            digests=[digests[0]],
        )
    )

    # The deleted version should not be readable
    with pytest.raises(ObjectDeletedError):
        internal.obj_read(
            tsi.ObjReadReq(
                project_id=project_id,
                object_id="multi-version-obj",
                digest=digests[0],
            )
        )

    # Other versions should still be readable and have version intact
    read_res_2 = internal.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="multi-version-obj",
            digest=digests[1],
        )
    )
    assert read_res_2.obj.version_index == 2

    read_res_3 = internal.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="multi-version-obj",
            digest=digests[2],
        )
    )
    assert read_res_3.obj.version_index == 3

    read_res_4 = internal.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="multi-version-obj",
            digest=digests[3],
        )
    )
    assert read_res_4.obj.val == {"version": 4}


def test_batch_upload_different_projects_should_error(trace_server):
    """Batch uploading to different projects in the same batch should throw an error."""
    internal = trace_server._internal_trace_server
    project_ext_1 = f"{TEST_ENTITY}/obj_batch_mixed_proj_1"
    project_ext_2 = f"{TEST_ENTITY}/obj_batch_mixed_proj_2"
    project_id_1 = _to_internal_id(project_ext_1)
    project_id_2 = _to_internal_id(project_ext_2)
    user_id = _to_internal_id("abc123")

    batch_req = tsi.ObjCreateBatchReq(
        batch=[
            tsi.ObjSchemaForInsert(
                project_id=project_id_1,
                object_id="obj-1",
                val={"a": 1},
                wb_user_id=user_id,
            ),
            tsi.ObjSchemaForInsert(
                project_id=project_id_2,
                object_id="obj-2",
                val={"b": 2},
                wb_user_id=user_id,
            ),
        ]
    )

    with pytest.raises(Exception):  # Server should enforce single-project batches
        internal.obj_create_batch(batch_req)
