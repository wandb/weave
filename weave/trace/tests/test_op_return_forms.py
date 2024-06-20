import pytest

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
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


def simple_list_accumulator(acc, value):
    if acc is None:
        acc = []
    acc.append(value)
    return acc


""" There are 16 tests that follow, permutations of the following:
    - (2x) sync/async
    - (2x) generator/iterator
    - (4x) never iterated/partially iterated/fully iterated/exception thrown
"""


def test_op_return_sync_generator(client):
    @weave.op()
    def fn():
        size = 10
        while size > 0:
            size -= 1
            yield size

    add_accumulator(fn, simple_list_accumulator)

    for item in fn():
        pass

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == list(range(9, -1, -1))


@pytest.mark.asyncio
async def test_op_return_async_generator(client):
    @weave.op()
    async def fn():
        size = 10
        while size > 0:
            size -= 1
            yield size

    add_accumulator(fn, simple_list_accumulator)

    async for item in fn():
        pass

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == list(range(9, -1, -1))


def test_op_return_sync_iterator(client):
    class MyIterator:
        size = 10

        def __iter__(self):
            return self

        def __next__(self):
            if self.size == 0:
                raise StopIteration
            self.size -= 1
            return self.size

    @weave.op()
    def fn():
        return MyIterator()

    add_accumulator(fn, simple_list_accumulator)

    for item in fn():
        pass

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == list(range(9, -1, -1))


@pytest.mark.asyncio
async def test_op_return_async_iterator(client):
    class MyAsyncIterator:
        size = 10

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.size == 0:
                raise StopAsyncIteration
            self.size -= 1
            return self.size

    @weave.op()
    def fn():
        return MyAsyncIterator()

    add_accumulator(fn, simple_list_accumulator)

    async for item in fn():
        pass

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == list(range(9, -1, -1))


def test_op_return_sync_generator_never_iter(client):
    @weave.op()
    def fn():
        size = 10
        while size > 0:
            size -= 1
            yield size

    add_accumulator(fn, simple_list_accumulator)

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
async def test_op_return_async_generator_never_iter(client):
    @weave.op()
    async def fn():
        size = 10
        while size > 0:
            size -= 1
            yield size

    add_accumulator(fn, simple_list_accumulator)

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


def test_op_return_sync_iterator_never_iter(client):
    class MyIterator:
        size = 10

        def __iter__(self):
            return self

        def __next__(self):
            if self.size == 0:
                raise StopIteration
            self.size -= 1
            return self.size

    @weave.op()
    def fn():
        return MyIterator()

    add_accumulator(fn, simple_list_accumulator)

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
async def test_op_return_async_iterator_never_iter(client):
    class MyAsyncIterator:
        size = 10

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.size == 0:
                raise StopAsyncIteration
            self.size -= 1
            return self.size

    @weave.op()
    def fn():
        return MyAsyncIterator()

    add_accumulator(fn, simple_list_accumulator)

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


def test_op_return_sync_generator_partial(client):
    @weave.op()
    def fn():
        size = 10
        while size > 0:
            size -= 1
            yield size

    add_accumulator(fn, simple_list_accumulator)

    for item in fn():
        if item == 5:
            break

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == list(range(9, 4, -1))


@pytest.mark.asyncio
async def test_op_return_async_generator_partial(client):
    @weave.op()
    async def fn():
        size = 10
        while size > 0:
            size -= 1
            yield size

    add_accumulator(fn, simple_list_accumulator)

    async for item in fn():
        if item == 5:
            break

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == list(range(9, 4, -1))


def test_op_return_sync_iterator_partial(client):
    class MyIterator:
        size = 10

        def __iter__(self):
            return self

        def __next__(self):
            if self.size == 0:
                raise StopIteration
            self.size -= 1
            return self.size

    @weave.op()
    def fn():
        return MyIterator()

    add_accumulator(fn, simple_list_accumulator)

    for item in fn():
        if item == 5:
            break

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == list(range(9, 4, -1))


@pytest.mark.asyncio
async def test_op_return_async_iterator_partial(client):
    class MyAsyncIterator:
        size = 10

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.size == 0:
                raise StopAsyncIteration
            self.size -= 1
            return self.size

    @weave.op()
    def fn():
        return MyAsyncIterator()

    add_accumulator(fn, simple_list_accumulator)

    async for item in fn():
        if item == 5:
            break

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == list(range(9, 4, -1))


def test_op_return_sync_generator_exception(client):
    @weave.op()
    def fn():
        size = 10
        while size > 0:
            size -= 1
            yield size
            if size == 5:
                raise Exception("test")

    add_accumulator(fn, simple_list_accumulator)

    try:
        for item in fn():
            pass
    except Exception:
        pass

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == list(range(9, 4, -1))
    assert res.calls[0].exception != None


@pytest.mark.asyncio
async def test_op_return_async_generator_exception(client):
    @weave.op()
    async def fn():
        size = 10
        while size > 0:
            size -= 1
            yield size
            if size == 5:
                raise Exception("test")

    add_accumulator(fn, simple_list_accumulator)

    try:
        async for item in fn():
            pass
    except Exception:
        pass

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == list(range(9, 4, -1))
    assert res.calls[0].exception != None


def test_op_return_sync_iterator_exception(client):
    class MyIterator:
        size = 10

        def __iter__(self):
            return self

        def __next__(self):
            if self.size == 0:
                raise StopIteration
            if self.size == 5:
                raise Exception("test")
            self.size -= 1
            return self.size

    @weave.op()
    def fn():
        return MyIterator()

    add_accumulator(fn, simple_list_accumulator)

    try:
        for item in fn():
            pass
    except Exception:
        pass

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == list(range(9, 4, -1))
    assert res.calls[0].exception != None


@pytest.mark.asyncio
async def test_op_return_async_iterator_exception(client):
    class MyAsyncIterator:
        size = 10

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.size == 0:
                raise StopAsyncIteration
            if self.size == 5:
                raise Exception("test")
            self.size -= 1
            return self.size

    @weave.op()
    def fn():
        return MyAsyncIterator()

    add_accumulator(fn, simple_list_accumulator)

    try:
        async for item in fn():
            pass
    except Exception:
        pass

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    obj_ref = get_ref(fn)
    assert obj_ref is not None
    assert res.calls[0].op_name == obj_ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == list(range(9, 4, -1))
    assert res.calls[0].exception != None
