import pytest

import weave
from weave.weave_client import get_ref

from ...trace_server import trace_server_interface as tsi


def test_op_return_sync_empty(client):
    @weave.op()
    def fn():
        return

    fn()

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

        
    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == None


@pytest.mark.asyncio
async def test_op_return_async_empty(client):
    @weave.op()
    async def fn():
        return

    await fn()

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

        
    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == None


def test_op_return_sync_obj(client):
    @weave.op()
    def fn():
        return 1

    fn()

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

        
    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == 1


@pytest.mark.asyncio
async def test_op_return_async_obj(client):
    @weave.op()
    async def fn():
        return 1

    await fn()

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == 1

