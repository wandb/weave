import pytest
import datetime

from weave.trace_server import trace_server_interface as tsi


def test_save_object(clickhouse_trace_server):
    create_res = clickhouse_trace_server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id="shawn/proj", name="my-obj", val={"a": 1}
            )
        )
    )
    read_res = clickhouse_trace_server.obj_read(
        tsi.ObjReadReq(
            entity="shawn",
            project="proj",
            name="my-obj",
            version_digest=create_res.version_digest,
        )
    )
