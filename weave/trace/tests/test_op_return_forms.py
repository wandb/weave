import pytest

import weave

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

    assert res.calls[0].op_name == fn.ref.uri()
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

    assert res.calls[0].op_name == fn.ref.uri()
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

    assert res.calls[0].op_name == fn.ref.uri()
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

    assert res.calls[0].op_name == fn.ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == 1


def test_op_return_sync_generator(client):
    @weave.op()
    def fn():
        size = 10
        while size > 0:
            size -= 1
            yield size

    for item in fn():
        pass

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == fn.ref.uri()
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

    async for item in fn():
        pass

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == fn.ref.uri()
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

    for item in fn():
        pass

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == fn.ref.uri()
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

    async for item in fn():
        pass

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == fn.ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == list(range(9, -1, -1))


def test_op_return_sync_generator_never_iter(client):
    @weave.op()
    def fn():
        size = 10
        while size > 0:
            size -= 1
            yield size

    fn()

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == fn.ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == []


@pytest.mark.asyncio
async def test_op_return_async_generator_never_iter(client):
    @weave.op()
    async def fn():
        size = 10
        while size > 0:
            size -= 1
            yield size

    fn()

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == fn.ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == []


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

    fn()

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == fn.ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == []


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

    fn()

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == fn.ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == []


def test_op_return_sync_generator_partial(client):
    @weave.op()
    def fn():
        size = 10
        while size > 0:
            size -= 1
            yield size

    for item in fn():
        if item == 5:
            break

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == fn.ref.uri()
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

    async for item in fn():
        if item == 5:
            break

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == fn.ref.uri()
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

    for item in fn():
        if item == 5:
            break

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == fn.ref.uri()
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

    async for item in fn():
        if item == 5:
            break

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == fn.ref.uri()
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

    assert res.calls[0].op_name == fn.ref.uri()
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

    assert res.calls[0].op_name == fn.ref.uri()
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

    for item in fn():
        if item == 5:
            break

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == fn.ref.uri()
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

    async for item in fn():
        if item == 5:
            break

    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
        )
    )

    assert res.calls[0].op_name == fn.ref.uri()
    assert res.calls[0].inputs == {}
    assert res.calls[0].output == list(range(9, 4, -1))
    assert res.calls[0].exception != None
