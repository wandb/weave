import asyncio
from typing import Coroutine

import pytest

import weave
from weave.trace.weave_client import Call


def test_non_async_non_coro(client):
    @weave.op()
    def non_async_non_coro():
        return 1

    res = non_async_non_coro()
    assert res == 1
    res, call = non_async_non_coro.call()
    assert isinstance(call, Call)
    assert res == 1


def test_non_async_non_coro_method(client):
    class TestClass:
        @weave.op()
        def non_async_non_coro(self):
            return 1

    test_inst = TestClass()
    res = test_inst.non_async_non_coro()
    assert res == 1
    res, call = test_inst.non_async_non_coro.call(test_inst)
    assert isinstance(call, Call)
    assert res == 1


@pytest.mark.asyncio
async def test_non_async_coro(client):
    @weave.op()
    def non_async_coro():
        return asyncio.to_thread(lambda: 1)

    res = non_async_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = non_async_coro.call()
    assert isinstance(call, Call)
    assert isinstance(res, Coroutine)
    assert await res == 1


@pytest.mark.asyncio
async def test_non_async_coro_method(client):
    class TestClass:
        @weave.op()
        def non_async_coro(self):
            return asyncio.to_thread(lambda: 1)

    test_inst = TestClass()
    res = test_inst.non_async_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = test_inst.non_async_coro.call(test_inst)
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
async def test_async_non_coro(client):
    @weave.op()
    async def async_non_coro():
        return 1

    res = async_non_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = await async_non_coro.call()
    assert isinstance(call, Call)
    assert res == 1


@pytest.mark.asyncio
async def test_async_non_coro_method(client):
    class TestClass:
        @weave.op()
        async def async_non_coro(self):
            return 1

    test_inst = TestClass()
    res = test_inst.async_non_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = await test_inst.async_non_coro.call(test_inst)
    assert isinstance(call, Call)
    assert res == 1


def test_non_async_with_exception(client):
    @weave.op()
    def non_async_with_exception():
        raise ValueError("test")

    with pytest.raises(ValueError, match="test"):
        non_async_with_exception()
    res, call = non_async_with_exception.call()
    assert isinstance(call, Call)
    assert call.exception is not None
    assert res == None


def test_non_async_with_exception_method(client):
    class TestClass:
        @weave.op()
        def non_async_with_exception(self):
            raise ValueError("test")

    test_inst = TestClass()
    with pytest.raises(ValueError, match="test"):
        test_inst.non_async_with_exception()
    res, call = test_inst.non_async_with_exception.call(test_inst)
    assert isinstance(call, Call)
    assert call.exception is not None
    assert res == None


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
    assert res == None


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
    assert res == None
