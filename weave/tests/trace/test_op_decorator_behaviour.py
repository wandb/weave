import inspect

import pytest

import weave
from weave.trace import errors
from weave.trace.op import Op, op
from weave.trace.refs import ObjectRef
from weave.trace.vals import MissingSelfInstanceError
from weave.weave_client import Call


@pytest.fixture
def func():
    @op
    def _func(a: int) -> int:
        return a + 1

    yield _func


@pytest.fixture
def afunc():
    @op
    async def _afunc(a: int) -> int:
        return a + 1

    yield _afunc


@pytest.fixture
def weave_obj():
    class A(weave.Object):
        @op
        def method(self, a: int) -> int:
            return a + 1

        @op
        async def amethod(self, a: int) -> int:
            return a + 1

    yield A()


@pytest.fixture
def py_obj():
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

    yield B()


def test_sync_func(client, func):
    assert func(1) == 2

    ref = weave.publish(func)
    func2 = ref.get()

    assert func2(1) == 2


def test_sync_func_call(client, func):
    res, call = func.call(1)
    assert isinstance(call, Call)
    assert call.inputs == {"a": 1}
    assert call.output == 2
    assert res == 2

    ref = weave.publish(func)
    func2 = ref.get()

    res2, call2 = func2.call(1)
    assert isinstance(call2, Call)
    assert call2.inputs == {"a": 1}
    assert call2.output == 2
    assert res2 == 2


@pytest.mark.asyncio
async def test_async_func(client, afunc):
    assert await afunc(1) == 2

    ref = weave.publish(afunc)
    afunc2 = ref.get()

    assert await afunc2(1) == 2


@pytest.mark.asyncio
async def test_async_func_call(client, afunc):
    res, call = await afunc.call(1)
    assert isinstance(call, Call)
    assert call.inputs == {"a": 1}
    assert call.output == 2
    assert res == 2

    ref = weave.publish(afunc)
    afunc2 = ref.get()

    res2, call2 = await afunc2.call(1)
    assert isinstance(call2, Call)
    assert call2.inputs == {"a": 1}
    assert call2.output == 2
    assert res2 == 2


def test_sync_method(client, weave_obj, py_obj):
    assert weave_obj.method(1) == 2
    assert py_obj.method(1) == 2

    weave_obj_method_ref = weave.publish(weave_obj.method)
    with pytest.raises(MissingSelfInstanceError):
        weave_obj_method2 = weave_obj_method_ref.get()


def test_sync_method_call(client, weave_obj, py_obj):
    res, call = weave_obj.method.call(1)
    assert isinstance(call, Call)
    assert call.inputs == {
        "self": ObjectRef(
            entity="shawn",
            project="test-project",
            name="A",
            digest="tGCIGNe9xznnkoJvn2i75TOocSfV7ui1vldSrIP3ZZo",
            extra=(),
        ),
        "a": 1,
    }
    assert call.output == 2
    assert res == 2

    weave_obj_method_ref = weave.publish(weave_obj.method)
    with pytest.raises(MissingSelfInstanceError):
        weave_obj_method2 = weave_obj_method_ref.get()

    with pytest.raises(errors.OpCallError):
        call2 = py_obj.amethod.call(1)


@pytest.mark.asyncio
async def test_async_method(client, weave_obj, py_obj):
    assert await weave_obj.amethod(1) == 2
    assert await py_obj.amethod(1) == 2

    weave_obj_amethod_ref = weave.publish(weave_obj.amethod)
    with pytest.raises(MissingSelfInstanceError):
        weave_obj_amethod2 = weave_obj_amethod_ref.get()


@pytest.mark.asyncio
async def test_async_method_call(client, weave_obj, py_obj):
    res, call = await weave_obj.amethod.call(1)
    assert isinstance(call, Call)
    assert call.inputs == {
        "self": ObjectRef(
            entity="shawn",
            project="test-project",
            name="A",
            digest="tGCIGNe9xznnkoJvn2i75TOocSfV7ui1vldSrIP3ZZo",
            extra=(),
        ),
        "a": 1,
    }
    assert call.output == 2
    assert res == 2

    weave_obj_amethod_ref = weave.publish(weave_obj.amethod)
    with pytest.raises(MissingSelfInstanceError):
        weave_obj_amethod2 = weave_obj_amethod_ref.get()

    with pytest.raises(errors.OpCallError):
        call2 = await py_obj.amethod.call(1)


def test_sync_func_patching_passes_inspection(func):
    assert isinstance(func, Op)
    assert inspect.isfunction(func)


def test_async_func_patching_passes_inspection(afunc):
    assert isinstance(afunc, Op)
    assert inspect.iscoroutinefunction(afunc)


def test_sync_method_patching_passes_inspection(weave_obj, py_obj):
    assert isinstance(weave_obj.method, Op)
    assert inspect.ismethod(weave_obj.method)

    assert isinstance(py_obj.method, Op)
    assert inspect.ismethod(py_obj.method)


def test_async_method_patching_passes_inspection(weave_obj, py_obj):
    assert isinstance(weave_obj.amethod, Op)
    assert inspect.iscoroutinefunction(weave_obj.amethod)
    assert inspect.ismethod(weave_obj.amethod)

    assert isinstance(py_obj.amethod, Op)
    assert inspect.iscoroutinefunction(py_obj.amethod)
    assert inspect.ismethod(py_obj.amethod)


def test_sync_method_calls(client, weave_obj):
    for x in range(3):
        weave_obj.method(x)

    for x in range(3):
        weave_obj.method.call(x)

    calls = weave_obj.method.calls()
    calls = list(calls)

    assert len(calls) == 6


@pytest.mark.asyncio
async def test_async_method_calls(client, weave_obj):
    for x in range(3):
        await weave_obj.amethod(x)

    for x in range(3):
        await weave_obj.amethod.call(x)

    calls = weave_obj.amethod.calls()
    calls = list(calls)

    assert len(calls) == 6


@pytest.mark.asyncio
async def test_gotten_object_method_is_callable(client, weave_obj):
    ref = weave.publish(weave_obj)

    weave_obj2 = ref.get()
    assert weave_obj.method(1) == weave_obj2.method(1) == 2
    assert await weave_obj.amethod(1) == await weave_obj2.amethod(1) == 2


@pytest.mark.asyncio
async def test_gotten_object_method_is_callable_with_call_func(client, weave_obj):
    ref = weave.publish(weave_obj)

    weave_obj2 = ref.get()
    res, call = weave_obj.method.call(1)
    res2, call2 = weave_obj2.method.call(1)
    assert res == res2
    assert call.inputs == call2.inputs
    assert call.output == call2.output

    res3, call3 = await weave_obj.amethod.call(1)
    res4, call4 = await weave_obj2.amethod.call(1)
    assert res3 == res4
    assert call3.inputs == call4.inputs
    assert call3.output == call4.output
