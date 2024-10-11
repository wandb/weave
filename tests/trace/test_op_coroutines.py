import asyncio
from typing import  Coroutine

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
    assert call.ended_at is not None
    assert res == 1
    assert call.ended_at is not None

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
    assert call.ended_at is not None
    assert isinstance(res, Coroutine)
    assert await res == 1
    assert call.ended_at is not None

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
    res, call = async_coro.call()
    assert isinstance(call, Call)
    assert call.ended_at is None # BIG DIFFERENCE! We haven't ended the outer op yet!
    assert isinstance(res, Coroutine)
    res2 = await res
    assert isinstance(res2, Coroutine) # Since we did not await the inner coroutine, we still have a coroutine here.
    assert await res2 == 1 
    assert call.ended_at is not None

@pytest.mark.asyncio
async def test_async_awaited_coro(client):
    @weave.op()
    async def async_awaited_coro():
        return await asyncio.to_thread(lambda: 1)
    
    res = async_awaited_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = async_awaited_coro.call()
    assert isinstance(call, Call)
    assert call.ended_at is None # BIG DIFFERENCE! We haven't ended the outer op yet!
    assert isinstance(res, Coroutine)
    assert await res == 1
    assert call.ended_at is not None


@pytest.mark.asyncio
async def test_async_non_coro(client):
    @weave.op()
    async def async_non_coro():
        return 1
    
    res = async_non_coro()
    assert isinstance(res, Coroutine)
    assert await res == 1
    res, call = async_non_coro.call()
    assert isinstance(call, Call)
    assert call.ended_at is None # BIG DIFFERENCE! We haven't ended the outer op yet!
    assert isinstance(res, Coroutine)
    assert await res == 1
    assert call.ended_at is not None