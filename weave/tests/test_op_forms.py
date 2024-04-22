import weave

from ..trace_server import trace_server_interface as tsi

def test_sync_(client):
    @weave.op()
    def my_op(a: int) -> int:
        return a + 1
    
    res = client.server.call_read(
        tsi.CallReadReq(
            project_id=client._project_id(),
        )
    )

    assert res.ops[0].name == "my_op"


# Args: Empty, Concrete, splat, concrete + splat, concrete + splat + concrete, concrete + splat + concrete + splat
# Returns: Empty, Object, Generator
# Schedule: Sync, Async
# Context: Normal, ContextManager

