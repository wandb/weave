import urllib

import pytest

from tests.trace.util import FAKE_NOT_IMPLEMENTED
from weave.shared.refs_internal import InvalidInternalRef
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import RefObjectsNotFoundError


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
    project_id = client.project_id
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


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_refs_read_batch_missing_refs_reports_digests(client):
    project_id = client.project_id
    create_res = client.server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=project_id, object_id="real-obj", val={"a": 1}
            )
        )
    )
    real_ref = f"weave:///{project_id}/object/real-obj:{create_res.digest}"
    missing_digest = "0" * 43
    missing_ref = f"weave:///{project_id}/object/missing-obj:{missing_digest}"

    # The missing object surfaces as a RefObjectsNotFoundError carrying the missing
    # digest as a structured field
    with pytest.raises(RefObjectsNotFoundError) as exc_info:
        client.server.refs_read_batch(
            tsi.RefsReadBatchReq(refs=[real_ref, missing_ref])
        )
    assert missing_digest in exc_info.value.missing_object_digests
