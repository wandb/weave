import inspect
from copy import deepcopy

import pytest

import weave
from weave.trace import errors
from weave.trace.op import Op, op
from weave.trace.refs import ObjectRef
from weave.weave_client import Call


@op
def func(a: int) -> int:
    return a + 1


@op
async def afunc(a: int) -> int:
    return a + 1


class A(weave.Object):
    @op
    def method(self, a: int) -> int:
        return a + 1

    @op
    async def amethod(self, a: int) -> int:
        return a + 1


class B:
    """
    special funcs (b.method.call, b.method.calls, etc.)
    wont work as expected because it's not a weave.Object
    """

    @op
    def method(self, a: int) -> int:
        return a + 1

    @op
    async def amethod(self, a: int) -> int:
        return a + 1


a = A()
b = B()


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
    assert b.method(1) == 2


def test_sync_method_call(client):
    call = a.method.call(1)
    assert isinstance(call, Call)
    assert call.inputs == {
        "self": ObjectRef(
            entity="shawn",
            project="test-project",
            name="A",
            digest="snOhb67iSQPwjzEaRXBQooMwcYrJ8EJ1r2XoXvqcVZI",
            extra=(),
        ),
        "a": 1,
    }
    assert call.output == 2

    with pytest.raises(errors.OpCallError):
        call2 = b.amethod.call(1)


@pytest.mark.asyncio
async def test_async_method(client):
    assert await a.amethod(1) == 2
    assert await b.amethod(1) == 2


@pytest.mark.asyncio
async def test_async_method_call(client):
    call = await a.amethod.call(1)
    assert isinstance(call, Call)
    assert call.inputs == {
        "self": ObjectRef(
            entity="shawn",
            project="test-project",
            name="A",
            digest="snOhb67iSQPwjzEaRXBQooMwcYrJ8EJ1r2XoXvqcVZI",
            extra=(),
        ),
        "a": 1,
    }
    assert call.output == 2

    with pytest.raises(errors.OpCallError):
        call2 = await b.amethod.call(1)


def test_sync_func_patching_passes_inspection():
    assert isinstance(func, Op)
    assert inspect.isfunction(func)


def test_async_func_patching_passes_inspection():
    assert isinstance(afunc, Op)
    assert inspect.iscoroutinefunction(afunc)


def test_sync_method_patching_passes_inspection():
    assert isinstance(a.method, Op)
    assert inspect.ismethod(a.method)

    assert isinstance(b.method, Op)
    assert inspect.ismethod(b.method)


def test_async_method_patching_passes_inspection():
    assert isinstance(a.amethod, Op)
    assert inspect.iscoroutinefunction(a.amethod)
    assert inspect.ismethod(a.amethod)

    assert isinstance(b.amethod, Op)
    assert inspect.iscoroutinefunction(b.amethod)
    assert inspect.ismethod(b.amethod)


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
