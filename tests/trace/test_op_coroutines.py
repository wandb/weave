import asyncio
from collections.abc import Coroutine

import pytest

import weave
from weave.trace.weave_client import Call


def test_sync_val(client):
    @weave.op()
    def sync_val():
        return 1

    res = sync_val()
    assert res == 1
    res, call = sync_val.call()
    assert isinstance(call, Call)
    assert res == 1


def test_sync_val_method(client):
    class TestClass:
        @weave.op()
        def sync_val(self):
            return 1

    test_inst = TestClass()
    res = test_inst.sync_val()
    assert res == 1
    res, call = test_inst.sync_val.call(test_inst)
    assert isinstance(call, Call)
    assert res == 1


@pytest.mark.asyncio
async def test_sync_coro(client):
    @weave.op()
    def sync_coro():
        return asyncio.to_thread(lambda: 1)

    res = sync_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = sync_coro.call()
    assert isinstance(call, Call)
    assert isinstance(res, Coroutine)
    assert await res == 1


@pytest.mark.asyncio
async def test_sync_coro_method(client):
    class TestClass:
        @weave.op()
        def sync_coro(self):
            return asyncio.to_thread(lambda: 1)

    test_inst = TestClass()
    res = test_inst.sync_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = test_inst.sync_coro.call(test_inst)
    assert isinstance(call, Call)
    assert isinstance(res, Coroutine)
    assert await res == 1


@pytest.mark.asyncio
async def test_async_coro(client):
    @weave.op()
    async def async_coro():
        return asyncio.to_thread(lambda: 1)

    res = async_coro()
    assert isinstance(res, Coroutine)
    res2 = await res
    assert isinstance(res2, Coroutine)
    assert await res2 == 1
    res, call = await async_coro.call()
    assert isinstance(call, Call)
    assert isinstance(res, Coroutine)
    assert await res == 1


@pytest.mark.asyncio
async def test_async_coro_method(client):
    class TestClass:
        @weave.op()
        async def async_coro(self):
            return asyncio.to_thread(lambda: 1)

    test_inst = TestClass()

    res = test_inst.async_coro()
    assert isinstance(res, Coroutine)
    res2 = await res
    assert isinstance(res2, Coroutine)
    assert await res2 == 1
    res, call = await test_inst.async_coro.call(test_inst)
    assert isinstance(call, Call)
    assert isinstance(res, Coroutine)
    assert await res == 1


@pytest.mark.asyncio
async def test_async_awaited_coro(client):
    @weave.op()
    async def async_awaited_coro():
        return await asyncio.to_thread(lambda: 1)

    res = async_awaited_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = await async_awaited_coro.call()
    assert isinstance(call, Call)
    assert res == 1


@pytest.mark.asyncio
async def test_async_awaited_coro_method(client):
    class TestClass:
        @weave.op()
        async def async_awaited_coro(self):
            return await asyncio.to_thread(lambda: 1)

    test_inst = TestClass()
    res = test_inst.async_awaited_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = await test_inst.async_awaited_coro.call(test_inst)
    assert isinstance(call, Call)
    assert res == 1


@pytest.mark.asyncio
async def test_async_val(client):
    @weave.op()
    async def async_val():
        return 1

    res = async_val()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = await async_val.call()
    assert isinstance(call, Call)
    assert res == 1


@pytest.mark.asyncio
async def test_async_val_method(client):
    class TestClass:
        @weave.op()
        async def async_val(self):
            return 1

    test_inst = TestClass()
    res = test_inst.async_val()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = await test_inst.async_val.call(test_inst)
    assert isinstance(call, Call)
    assert res == 1


def test_sync_with_exception(client):
    @weave.op()
    def sync_with_exception():
        raise ValueError("test")

    with pytest.raises(ValueError, match="test"):
        sync_with_exception()
    res, call = sync_with_exception.call()
    assert isinstance(call, Call)
    assert call.exception is not None
    assert res is None


def test_sync_with_exception_method(client):
    class TestClass:
        @weave.op()
        def sync_with_exception(self):
            raise ValueError("test")

    test_inst = TestClass()
    with pytest.raises(ValueError, match="test"):
        test_inst.sync_with_exception()
    res, call = test_inst.sync_with_exception.call(test_inst)
    assert isinstance(call, Call)
    assert call.exception is not None
    assert res is None


@pytest.mark.asyncio
async def test_async_with_exception(client):
    @weave.op()
    async def async_with_exception():
        raise ValueError("test")

    with pytest.raises(ValueError, match="test"):
        await async_with_exception()
    res, call = await async_with_exception.call()
    assert isinstance(call, Call)
    assert call.exception is not None
    assert res is None


@pytest.mark.asyncio
async def test_async_with_exception_method(client):
    class TestClass:
        @weave.op()
        async def async_with_exception(self):
            raise ValueError("test")

    test_inst = TestClass()
    with pytest.raises(ValueError, match="test"):
        await test_inst.async_with_exception()
    res, call = await test_inst.async_with_exception.call(test_inst)
    assert isinstance(call, Call)
    assert call.exception is not None
    assert res is None
