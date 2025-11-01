import asyncio
from collections.abc import Coroutine

import pytest

import weave
from weave.trace.call import Call


def test_sync_val(client):
    @weave.op
    def sync_val():
        return 1

    res = sync_val()
    assert res == 1
    res, call = sync_val.call()
    assert isinstance(call, Call)
    assert res == 1


def test_sync_val_method(client):
    class TestClass:
        @weave.op
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
    @weave.op
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
        @weave.op
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
    @weave.op
    async def async_coro():
        return asyncio.to_thread(lambda: 1)

    res = async_coro()
    assert isinstance(res, Coroutine)
    res2 = await res
    assert isinstance(res2, Coroutine)
    assert await res2 == 1
    coro, call = async_coro.call()
    assert isinstance(call, Call)
    assert isinstance(coro, Coroutine)
    res, call = await coro
    assert isinstance(res, Coroutine)
    assert await res == 1


@pytest.mark.asyncio
async def test_async_coro_method(client):
    class TestClass:
        @weave.op
        async def async_coro(self):
            return asyncio.to_thread(lambda: 1)

    test_inst = TestClass()

    res = test_inst.async_coro()
    assert isinstance(res, Coroutine)
    res2 = await res
    assert isinstance(res2, Coroutine)
    assert await res2 == 1
    coro, call = test_inst.async_coro.call(test_inst)
    assert isinstance(call, Call)
    assert isinstance(coro, Coroutine)
    res, call = await coro
    assert isinstance(res, Coroutine)
    assert await res == 1


@pytest.mark.asyncio
async def test_async_awaited_coro(client):
    @weave.op
    async def async_awaited_coro():
        return await asyncio.to_thread(lambda: 1)

    res = async_awaited_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    coro, call = async_awaited_coro.call()
    assert isinstance(call, Call)
    res, call = await coro
    assert res == 1


@pytest.mark.asyncio
async def test_async_awaited_coro_method(client):
    class TestClass:
        @weave.op
        async def async_awaited_coro(self):
            return await asyncio.to_thread(lambda: 1)

    test_inst = TestClass()
    res = test_inst.async_awaited_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    coro, call = test_inst.async_awaited_coro.call(test_inst)
    assert isinstance(call, Call)
    res, call = await coro
    assert res == 1


@pytest.mark.asyncio
async def test_async_val(client):
    @weave.op
    async def async_val():
        return 1

    res = async_val()
    assert isinstance(res, Coroutine)
    assert await res == 1
    coro, call = async_val.call()
    assert isinstance(call, Call)
    res, call = await coro
    assert res == 1


@pytest.mark.asyncio
async def test_async_val_method(client):
    class TestClass:
        @weave.op
        async def async_val(self):
            return 1

    test_inst = TestClass()
    res = test_inst.async_val()
    assert isinstance(res, Coroutine)
    assert await res == 1
    coro, call = test_inst.async_val.call(test_inst)
    assert isinstance(call, Call)
    res, call = await coro
    assert res == 1


def test_sync_with_exception(client):
    @weave.op
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
        @weave.op
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
    @weave.op
    async def async_with_exception():
        raise ValueError("test")

    with pytest.raises(ValueError, match="test"):
        await async_with_exception()
    coro, call = async_with_exception.call()
    assert isinstance(call, Call)
    res, call = await coro
    assert call.exception is not None
    assert res is None


@pytest.mark.asyncio
async def test_async_with_exception_method(client):
    class TestClass:
        @weave.op
        async def async_with_exception(self):
            raise ValueError("test")

    test_inst = TestClass()
    with pytest.raises(ValueError, match="test"):
        await test_inst.async_with_exception()
    coro, call = test_inst.async_with_exception.call(test_inst)
    assert isinstance(call, Call)
    res, call = await coro
    assert call.exception is not None
    assert res is None


@pytest.mark.asyncio
async def test_get_call_for_coroutine(client):
    """Test getting Call object for a coroutine that has started but not finished."""
    call_ids = []

    @weave.op
    async def slow_op(x: int) -> int:
        # Store the call ID while the op is running
        current_call = weave.get_current_call()
        if current_call:
            call_ids.append(current_call.id)
        await asyncio.sleep(0.1)
        return x * 2

    # Test Option 1: Get coroutine and call immediately via call()
    coro, call = slow_op.call(5)
    assert call is not None
    assert isinstance(call, Call)
    assert call.id is not None

    # Create a task to start execution
    task = asyncio.create_task(coro)

    # Wait a bit for the coroutine to start
    await asyncio.sleep(0.01)

    # The Call object should match what we got from call()
    call_during_execution = weave.get_call_for_coroutine(coro)
    assert call_during_execution is not None
    assert call_during_execution.id == call.id
    assert call_during_execution.id == call_ids[0]

    # Wait for completion
    result, call_after_completion = await task
    assert result == 10
    assert call_after_completion.id == call.id

    # Test Option 2: Using get_call_for_coroutine with direct call
    coro2 = slow_op(5)
    task2 = asyncio.create_task(coro2)

    # Wait a bit for the coroutine to start
    await asyncio.sleep(0.01)

    # Get the Call object while running
    call2 = weave.get_call_for_coroutine(coro2)
    assert call2 is not None
    assert isinstance(call2, Call)

    # Wait for completion
    result2 = await task2
    assert result2 == 10
