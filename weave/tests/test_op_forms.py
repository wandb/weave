from ..trace_server import trace_server_interface as tsi

def test_simple_op(client):
    @weave.op()
    def my_op(a: int) -> int:
        return a + 1
    
    res = client.server.call_read(
        tsi.CallReadReq(
            project_id=client._project_id(),
        )
    )

    assert res.ops[0].name == "my_op"
