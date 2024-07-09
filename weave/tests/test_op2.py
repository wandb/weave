import inspect

import pytest

from weave.trace.op import Op2, op2
from weave.weave_client import Call


@op2
def func(a: int) -> int:
    return a + 1


@op2
async def afunc(a: int) -> int:
    return a + 1


class A:
    @op2
    def method(self, a: int) -> int:
        return a + 1

    @op2
    async def amethod(self, a: int) -> int:
        return a + 1


a = A()


def test_sync_func(client):
    assert func(1) == 2


def test_sync_func_call(client):
    call = func.call(1)
    assert isinstance(call, Call)
    assert call.inputs == {"a": 1}
    assert call.output == 2


@pytest.mark.asyncio
async def test_async_func(client):
    assert await afunc(1) == 2


@pytest.mark.asyncio
async def test_async_func_call(client):
    call = await afunc.call(1)
    assert isinstance(call, Call)
    assert call.inputs == {"a": 1}
    assert call.output == 2


def test_sync_method(client):
    assert a.method(1) == 2


def test_sync_method_call(client):
    call = a.method.call(1)
    assert isinstance(call, Call)
    # assert call.inputs == {"self": a, "a": 1}  # self is an opref?  Is that expected?
    assert call.output == 2


@pytest.mark.asyncio
async def test_async_method(client):
    assert await a.amethod(1) == 2


@pytest.mark.asyncio
async def test_async_method_call(client):
    call = await a.amethod.call(1)
    assert isinstance(call, Call)
    # assert call.inputs == {"self": a, "a": 1}  # self is an opref?  Is that expected?
    assert call.output == 2


def test_sync_func_patching_passes_inspection():
    assert isinstance(func, Op2)
    assert inspect.isfunction(func)


def test_async_func_patching_passes_inspection():
    assert isinstance(afunc, Op2)
    assert inspect.iscoroutinefunction(afunc)


def test_sync_method_patching_passes_inspection():
    assert isinstance(a.method, Op2)
    assert inspect.ismethod(a.method)


def test_async_method_patching_passes_inspection():
    assert isinstance(a.amethod, Op2)
    assert inspect.iscoroutinefunction(a.amethod)
    assert inspect.ismethod(a.amethod)


def test_sync_method_calls(client):
    for x in range(3):
        a.method(x)

    for x in range(3):
        a.method.call(x)

    calls = a.method.calls()
    calls = list(calls)

    assert len(calls) == 6


@pytest.mark.asyncio
async def test_async_method_calls(client):
    for x in range(3):
        await a.amethod(x)

    for x in range(3):
        await a.amethod.call(x)

    calls = a.amethod.calls()
    calls = list(calls)

    assert len(calls) == 6
