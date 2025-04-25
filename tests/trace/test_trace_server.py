import urllib

import pytest

import weave
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
    with pytest.raises(Exception):
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


def test_project_check(client):
    # real project, no data
    proj = client._project_id()
    res = client.server.project_check(tsi.ProjectCheckReq(project_id=proj))
    assert not res.has_data

    # fake project
    res = client.server.project_check(
        tsi.ProjectCheckReq(project_id="shawn/proj-does-not-exist")
    )
    assert not res.has_data

    # real project w/ just calls data
    @weave.op
    def log():
        return "a"

    log()

    res = client.server.project_check(tsi.ProjectCheckReq(project_id=proj))
    assert res.has_data

    # new project, no data
    client.project = "new-project"
    project2 = f"{client.entity}/{client.project}"
    res = client.server.project_check(tsi.ProjectCheckReq(project_id=project2))
    assert not res.has_data

    # real project w/ just object data
    obj = {"a": 1}
    client.save(obj, "o")

    res = client.server.project_check(tsi.ProjectCheckReq(project_id=project2))
    assert res.has_data

    # both
    @weave.op
    def log2():
        return "a"

    log2()

    res = client.server.project_check(tsi.ProjectCheckReq(project_id=project2))
    assert res.has_data
