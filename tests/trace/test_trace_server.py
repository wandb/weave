import urllib

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.refs_internal import InvalidInternalRef
from weave.trace_server.errors import ObjectDeletedError


def test_save_object(client):
    create_res = client.server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id="shawn/proj", object_id="my-obj", val={"a": 1}
            )
        )
    )
    read_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id="shawn/proj",
            object_id="my-obj",
            digest=create_res.digest,
        )
    )

    assert read_res.obj.val == {"a": 1}


def test_robust_to_url_sensitive_chars(client):
    project_id = client._project_id()
    object_id = "mali_cious-obj.ect"
    bad_key = "mali:cious/ke%y"
    bad_val = {bad_key: "hello world"}

    create_res = client.server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id=object_id,
                val=bad_val,
            )
        )
    )

    read_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id=object_id,
            digest=create_res.digest,
        )
    )

    assert read_res.obj.val == bad_val

    # Object ID that contains reserved characters should be rejected.

    read_res = client.server.refs_read_batch(
        tsi.RefsReadBatchReq(
            refs=[f"weave:///{project_id}/object/{object_id}:{create_res.digest}"]
        )
    )

    assert read_res.vals[0] == bad_val

    # Key that contains reserved characters should be rejected.
    with pytest.raises(InvalidInternalRef):
        read_res = client.server.refs_read_batch(
            tsi.RefsReadBatchReq(
                refs=[
                    f"weave:///{project_id}/object/{object_id}:{create_res.digest}/key/{bad_key}"
                ]
            )
        )

    encoded_bad_key = urllib.parse.quote_plus(bad_key)
    assert encoded_bad_key == "mali%3Acious%2Fke%25y"
    read_res = client.server.refs_read_batch(
        tsi.RefsReadBatchReq(
            refs=[
                f"weave:///{project_id}/object/{object_id}:{create_res.digest}/key/{encoded_bad_key}"
            ]
        )
    )
    assert read_res.vals[0] == bad_val[bad_key]


def test_save_object_batch(client):
    project_id = client._project_id()
    batch_req = tsi.ObjCreateBatchReq(
        batch=[
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="obj-a",
                val={"a": 1},
                wb_user_id="abc123",
            ),
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="obj-b",
                val={"b": 2},
                wb_user_id="abc123",
            ),
        ]
    )

    create_batch_res = client.server.obj_create_batch(batch_req)

    assert len(create_batch_res.results) == 2

    # Read back and verify values match
    for expected_oid, expected_val, res in zip(
        ["obj-a", "obj-b"], [{"a": 1}, {"b": 2}], create_batch_res.results
    ):
        assert res.object_id == expected_oid

        read_res = client.server.obj_read(
            tsi.ObjReadReq(
                project_id=project_id,
                object_id=expected_oid,
                digest=res.digest,
            )
        )
        assert read_res.obj.val == expected_val


def test_robust_to_url_sensitive_chars_batch(client):
    project_id = client._project_id()
    object_id = "mali_cious-obj.ect"
    bad_key = "mali:cious/ke%y"
    bad_val = {bad_key: "hello world"}

    # Create two objects via batch, one with URL-sensitive chars in keys
    create_batch_res = client.server.obj_create_batch(
        tsi.ObjCreateBatchReq(
            batch=[
                tsi.ObjSchemaForInsert(
                    project_id=project_id,
                    object_id=object_id,
                    val=bad_val,
                    wb_user_id="abc123",
                ),
                tsi.ObjSchemaForInsert(
                    project_id=project_id,
                    object_id="normal",
                    val={"x": 1},
                    wb_user_id="abc123",
                ),
            ]
        )
    )

    # Validate read by ref works for the object with special key
    created = create_batch_res.results[0]

    read_res = client.server.refs_read_batch(
        tsi.RefsReadBatchReq(
            refs=[f"weave:///{project_id}/object/{object_id}:{created.digest}"]
        )
    )
    assert read_res.vals[0] == bad_val

    # Using a non-encoded key in ref path should raise
    with pytest.raises(InvalidInternalRef):
        client.server.refs_read_batch(
            tsi.RefsReadBatchReq(
                refs=[
                    f"weave:///{project_id}/object/{object_id}:{created.digest}/key/{bad_key}"
                ]
            )
        )

    encoded_bad_key = urllib.parse.quote_plus(bad_key)
    assert encoded_bad_key == "mali%3Acious%2Fke%25y"
    read_res = client.server.refs_read_batch(
        tsi.RefsReadBatchReq(
            refs=[
                f"weave:///{project_id}/object/{object_id}:{created.digest}/key/{encoded_bad_key}"
            ]
        )
    )
    assert read_res.vals[0] == bad_val[bad_key]


def test_batch_upload_same_object_id_different_hash(client):
    """Test batch uploading two objects with the same object_id but different hash."""
    project_id = client._project_id()

    batch_req = tsi.ObjCreateBatchReq(
        batch=[
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="same-obj",
                val={"version": 1},
                wb_user_id="abc123",
            ),
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="same-obj",
                val={"version": 2},
                wb_user_id="abc123",
            ),
        ]
    )

    create_batch_res = client.server.obj_create_batch(batch_req)

    assert len(create_batch_res.results) == 2

    # Should have different digests since values are different
    digest_1 = create_batch_res.results[0].digest
    digest_2 = create_batch_res.results[1].digest
    assert digest_1 != digest_2

    # Both versions should be readable
    read_res_1 = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="same-obj",
            digest=digest_1,
        )
    )
    assert read_res_1.obj.val == {"version": 1}

    read_res_2 = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="same-obj",
            digest=digest_2,
        )
    )
    assert read_res_2.obj.val == {"version": 2}


def test_batch_upload_same_hash_different_object_id(client):
    """Test batch uploading objects with same hash but different object_id."""
    project_id = client._project_id()
    same_val = {"data": "identical"}

    batch_req = tsi.ObjCreateBatchReq(
        batch=[
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="obj-1",
                val=same_val,
                wb_user_id="abc123",
            ),
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="obj-2",
                val=same_val,
                wb_user_id="abc123",
            ),
        ]
    )

    create_batch_res = client.server.obj_create_batch(batch_req)

    assert len(create_batch_res.results) == 2

    # Should have same digest since values are identical
    digest_1 = create_batch_res.results[0].digest
    digest_2 = create_batch_res.results[1].digest
    assert digest_1 == digest_2

    # Both object_ids should be different
    assert create_batch_res.results[0].object_id == "obj-1"
    assert create_batch_res.results[1].object_id == "obj-2"

    # Both should be readable with their respective object_ids
    read_res_1 = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="obj-1",
            digest=digest_1,
        )
    )
    assert read_res_1.obj.val == same_val

    read_res_2 = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="obj-2",
            digest=digest_2,
        )
    )
    assert read_res_2.obj.val == same_val


def test_batch_upload_identical_object_id_and_hash(client):
    """Test batch uploading identical objects (same object_id and hash)."""
    project_id = client._project_id()
    identical_val = {"data": "same"}

    batch_req = tsi.ObjCreateBatchReq(
        batch=[
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="identical-obj",
                val=identical_val,
                wb_user_id="abc123",
            ),
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="identical-obj",
                val=identical_val,
                wb_user_id="abc123",
            ),
        ]
    )

    create_batch_res = client.server.obj_create_batch(batch_req)

    assert len(create_batch_res.results) == 2

    # Should have identical results (idempotent)
    digest_1 = create_batch_res.results[0].digest
    digest_2 = create_batch_res.results[1].digest
    assert digest_1 == digest_2
    assert create_batch_res.results[0].object_id == create_batch_res.results[1].object_id

    # Should be readable
    read_res = client.server.obj_read(
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
    assert len(client.server.objs_query(obj_query_req).objs) == 1


def test_batch_upload_multiple_versions_then_read(client):
    """Test batch uploading 4 versions of the same object, then confirm read path works."""
    project_id = client._project_id()

    batch_req = tsi.ObjCreateBatchReq(
        batch=[
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="versioned-obj",
                val={"version": i},
                wb_user_id="abc123",
            )
            for i in range(1, 5)
        ]
    )

    create_batch_res = client.server.obj_create_batch(batch_req)

    assert len(create_batch_res.results) == 4

    # All digests should be different
    digests = [res.digest for res in create_batch_res.results]
    assert len(set(digests)) == 4, "All versions should have unique digests"

    # All versions should be readable
    for i, digest in enumerate(digests, start=1):
        read_res = client.server.obj_read(
            tsi.ObjReadReq(
                project_id=project_id,
                object_id="versioned-obj",
                digest=digest,
            )
        )
        assert read_res.obj.val == {"version": i}


def test_batch_upload_delete_version_with_multiple_versions(client):
    """Test deleting an object version for an object with multiple versions after batch uploading."""
    project_id = client._project_id()

    # Create multiple versions via batch
    batch_req = tsi.ObjCreateBatchReq(
        batch=[
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id="multi-version-obj",
                val={"version": i},
                wb_user_id="abc123",
            )
            for i in range(1, 5)
        ]
    )

    create_batch_res = client.server.obj_create_batch(batch_req)

    assert len(create_batch_res.results) == 4
    digests = [res.digest for res in create_batch_res.results]

    # Delete the middle version
    client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=project_id,
            object_id="multi-version-obj",
            digests=[digests[0]],
        )
    )

    # The deleted version should not be readable
    with pytest.raises(ObjectDeletedError):
        client.server.obj_read(
            tsi.ObjReadReq(
                project_id=project_id,
                object_id="multi-version-obj",
                digest=digests[0],
            )
        )

    # Other versions should still be readable
    read_res_2 = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="multi-version-obj",
            digest=digests[1],
        )
    )
    assert read_res_2.obj.val == {"version": 2}

    read_res_3 = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="multi-version-obj",
            digest=digests[2],
        )
    )
    assert read_res_3.obj.val == {"version": 3}

    read_res_4 = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id="multi-version-obj",
            digest=digests[3],
        )
    )
    assert read_res_4.obj.val == {"version": 4}

def test_batch_upload_different_projects_should_error(client):
    """Test that batch uploading to different projects in the same batch throws an error."""
    project_id_1 = client._project_id()
    project_id_2 = "different/project"

    batch_req = tsi.ObjCreateBatchReq(
        batch=[
            tsi.ObjSchemaForInsert(
                project_id=project_id_1,
                object_id="obj-1",
                val={"a": 1},
                wb_user_id="abc123",
            ),
            tsi.ObjSchemaForInsert(
                project_id=project_id_2,
                object_id="obj-2",
                val={"b": 2},
                wb_user_id="abc123",
            ),
        ]
    )

    # Should raise an error due to different projects in same batch
    with pytest.raises(Exception):  # Adjust exception type as needed
        client.server.obj_create_batch(batch_req)
