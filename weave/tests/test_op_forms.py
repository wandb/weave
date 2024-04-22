import weave

from ..trace_server import trace_server_interface as tsi


def test_args_empty(client):
    @weave.op()
    def my_op() -> int:
        return 1
    
    my_op()

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == my_op.ref.uri()
    assert res.calls[0].inputs == {}

def test_args_concrete(client):
    @weave.op()
    def my_op(val) -> int:
        return [val]
    
    my_op(1)

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == my_op.ref.uri()
    assert res.calls[0].inputs == {'val': 1}
    assert res.calls[0].output == [1]



def test_args_concrete_splat(client):
    @weave.op()
    def my_op(val, *args) -> int:
        return [val, args]
    
    my_op(1)
    my_op(1, 2, 3)

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == my_op.ref.uri()
    assert res.calls[0].inputs == {'val': 1, 'args': []}
    assert res.calls[0].output == [1, []]
    assert res.calls[1].op_name == my_op.ref.uri()
    assert res.calls[1].inputs == {'val': 1, 'args': [2, 3]}
    assert res.calls[1].output == [1, [2, 3]]

def test_args_concrete_splats(client):
    @weave.op()
    def my_op(val, *args, **kwargs) -> int:
        return [val, args, kwargs]
    
    my_op(1)
    my_op(1, 2, 3)
    my_op(1, a=2, b=3)
    my_op(1, 2, 3, a=4, b=5)

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == my_op.ref.uri()
    assert res.calls[0].inputs == {'val': 1, 'args': [], 'kwargs': {}}
    assert res.calls[0].output == [1, [], {}]
    assert res.calls[1].op_name == my_op.ref.uri()
    assert res.calls[1].inputs == {'val': 1, 'args': [2, 3], 'kwargs': {}}
    assert res.calls[1].output == [1, [2, 3], {}]
    assert res.calls[2].op_name == my_op.ref.uri()
    assert res.calls[2].inputs == {'val': 1, 'args': [], 'kwargs': {'a': 2, 'b': 3}}
    assert res.calls[2].output == [1, [], {'a': 2, 'b': 3}]
    assert res.calls[3].op_name == my_op.ref.uri()
    assert res.calls[3].inputs == {'val': 1, 'args': [2, 3], 'kwargs': {'a': 4, 'b': 5}}
    assert res.calls[3].output == [1, [2, 3], {'a': 4, 'b': 5}]


def test_args_concrete_splat_concrete(client):
    @weave.op()
    def my_op(val, *args, a=0) -> int:
        return [val, args, a]
    
    my_op(1)
    my_op(1, a=2)
    my_op(1, 2, 3, a=4)

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == my_op.ref.uri()
    assert res.calls[0].inputs == {'val': 1, 'args': [], 'a': 0}
    assert res.calls[0].output == [1, [], 0]
    assert res.calls[1].op_name == my_op.ref.uri()
    assert res.calls[1].inputs == {'val': 1, 'args': [], 'a': 2}
    assert res.calls[1].output == [1, [], 2]
    assert res.calls[2].op_name == my_op.ref.uri()
    assert res.calls[2].inputs == {'val': 1, 'args': [2, 3], 'a': 4}
    assert res.calls[2].output == [1, [2, 3], 4]


def test_args_concrete_splat_concrete_splat(client):
    @weave.op()
    def my_op(val, *args, a=0, **kwargs) -> int:
        return [val, args, a, kwargs]
    
    my_op(1)
    my_op(1, a=2)
    my_op(1, 2, 3, a=4)
    my_op(1, 2, 3, a=4, b=5)

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == my_op.ref.uri()
    assert res.calls[0].inputs == {'val': 1, 'args': [], 'a': 0, 'kwargs': {}}
    assert res.calls[0].output == [1, [], 0, {}]
    assert res.calls[1].op_name == my_op.ref.uri()
    assert res.calls[1].inputs == {'val': 1, 'args': [], 'a': 2, 'kwargs': {}}
    assert res.calls[1].output == [1, [], 2, {}]
    assert res.calls[2].op_name == my_op.ref.uri()
    assert res.calls[2].inputs == {'val': 1, 'args': [2, 3], 'a': 4, 'kwargs': {}}
    assert res.calls[2].output == [1, [2, 3], 4, {}]
    assert res.calls[3].op_name == my_op.ref.uri()
    assert res.calls[3].inputs == {'val': 1, 'args': [2, 3], 'a': 4, 'kwargs': {'b': 5}}
    assert res.calls[3].output == [1, [2, 3], 4, {'b': 5}]


# Args: Empty, Concrete, splat, concrete + splat, concrete + splat + concrete, concrete + splat + concrete + splat
# Returns: Empty, Object, Generator
# Schedule: Sync, Async
# Context: Normal, ContextManager

