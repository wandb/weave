import urllib

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.refs_internal import InvalidInternalRef


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
