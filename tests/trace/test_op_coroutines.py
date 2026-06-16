import asyncio
from collections.abc import Coroutine

import pytest

import weave
from weave.trace.call import Call


def test_sync_val(weave_active):
    """A sync op returning a plain value, as a free function and as a method."""

    @weave.op
    def sync_val():
        return 1

    class TestClass:
        @weave.op
        def sync_val(self):
            return 1

    assert sync_val() == 1
    res, call = sync_val.call()
    assert isinstance(call, Call)
    assert res == 1

    inst = TestClass()
    assert inst.sync_val() == 1
    res, call = inst.sync_val.call(inst)
    assert isinstance(call, Call)
    assert res == 1


@pytest.mark.asyncio
async def test_sync_coro(weave_active):
    """A sync op returning a coroutine, as a free function and as a method."""

    @weave.op
    def sync_coro():
        return asyncio.to_thread(lambda: 1)

    class TestClass:
        @weave.op
        def sync_coro(self):
            return asyncio.to_thread(lambda: 1)

    res = sync_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = sync_coro.call()
    assert isinstance(call, Call)
    assert isinstance(res, Coroutine)
    assert await res == 1

    inst = TestClass()
    res = inst.sync_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = inst.sync_coro.call(inst)
    assert isinstance(call, Call)
    assert isinstance(res, Coroutine)
    assert await res == 1


@pytest.mark.asyncio
async def test_async_coro(weave_active):
    """An async op returning a coroutine (double-wrapped), as a free function and a method."""

    @weave.op
    async def async_coro():
        return asyncio.to_thread(lambda: 1)

    class TestClass:
        @weave.op
        async def async_coro(self):
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

    inst = TestClass()
    res = inst.async_coro()
    assert isinstance(res, Coroutine)
    res2 = await res
    assert isinstance(res2, Coroutine)
    assert await res2 == 1
    res, call = await inst.async_coro.call(inst)
    assert isinstance(call, Call)
    assert isinstance(res, Coroutine)
    assert await res == 1


@pytest.mark.asyncio
async def test_async_awaited_coro(weave_active):
    """An async op that awaits internally, returning a value, as a free function and a method."""

    @weave.op
    async def async_awaited_coro():
        return await asyncio.to_thread(lambda: 1)

    class TestClass:
        @weave.op
        async def async_awaited_coro(self):
            return await asyncio.to_thread(lambda: 1)

    res = async_awaited_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = await async_awaited_coro.call()
    assert isinstance(call, Call)
    assert res == 1

    inst = TestClass()
    res = inst.async_awaited_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = await inst.async_awaited_coro.call(inst)
    assert isinstance(call, Call)
    assert res == 1


@pytest.mark.asyncio
async def test_async_val(weave_active):
    """An async op returning a plain value, as a free function and as a method."""

    @weave.op
    async def async_val():
        return 1

    class TestClass:
        @weave.op
        async def async_val(self):
            return 1

    res = async_val()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = await async_val.call()
    assert isinstance(call, Call)
    assert res == 1

    inst = TestClass()
    res = inst.async_val()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = await inst.async_val.call(inst)
    assert isinstance(call, Call)
    assert res == 1


def test_sync_with_exception(weave_active):
    """A sync op that raises records the exception on the call, as a free function and a method."""

    @weave.op
    def sync_with_exception():
        raise ValueError("test")

    class TestClass:
        @weave.op
        def sync_with_exception(self):
            raise ValueError("test")

    with pytest.raises(ValueError, match="test"):
        sync_with_exception()
    res, call = sync_with_exception.call()
    assert isinstance(call, Call)
    assert call.exception is not None
    assert res is None

    inst = TestClass()
    with pytest.raises(ValueError, match="test"):
        inst.sync_with_exception()
    res, call = inst.sync_with_exception.call(inst)
    assert isinstance(call, Call)
    assert call.exception is not None
    assert res is None


@pytest.mark.asyncio
async def test_async_with_exception(weave_active):
    """An async op that raises records the exception on the call, as a free function and a method."""

    @weave.op
    async def async_with_exception():
        raise ValueError("test")

    class TestClass:
        @weave.op
        async def async_with_exception(self):
            raise ValueError("test")

    with pytest.raises(ValueError, match="test"):
        await async_with_exception()
    res, call = await async_with_exception.call()
    assert isinstance(call, Call)
    assert call.exception is not None
    assert res is None

    inst = TestClass()
    with pytest.raises(ValueError, match="test"):
        await inst.async_with_exception()
    res, call = await inst.async_with_exception.call(inst)
    assert isinstance(call, Call)
    assert call.exception is not None
    assert res is None
