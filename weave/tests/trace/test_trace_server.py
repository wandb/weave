import urllib

import pytest

from weave.trace_server import trace_server_interface as tsi


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
    entity = "entity"
    project = "project"
    project_id = f"{entity}/{project}"
    object_id = "mali:cious/obj%ect"
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
    with pytest.raises(Exception):
        read_res = client.server.refs_read_batch(
            tsi.RefsReadBatchReq(
                refs=[f"weave:///{project_id}/object/{object_id}:{create_res.digest}"]
            )
        )

    encoded_object_id = urllib.parse.quote_plus(object_id)
    assert encoded_object_id == "mali%3Acious%2Fobj%25ect"
    read_res = client.server.refs_read_batch(
        tsi.RefsReadBatchReq(
            refs=[
                f"weave:///{project_id}/object/{encoded_object_id}:{create_res.digest}"
            ]
        )
    )
    assert read_res.vals[0] == bad_val

    # Key that contains reserved characters should be rejected.
    with pytest.raises(Exception):
        read_res = client.server.refs_read_batch(
            tsi.RefsReadBatchReq(
                refs=[
                    f"weave:///{project_id}/object/{encoded_object_id}:{create_res.digest}/key/{bad_key}"
                ]
            )
        )

    encoded_bad_key = urllib.parse.quote_plus(bad_key)
    assert encoded_bad_key == "mali%3Acious%2Fke%25y"
    read_res = client.server.refs_read_batch(
        tsi.RefsReadBatchReq(
            refs=[
                f"weave:///{project_id}/object/{encoded_object_id}:{create_res.digest}/key/{encoded_bad_key}"
            ]
        )
    )
    assert read_res.vals[0] == bad_val[bad_key]
