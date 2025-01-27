import inspect
from typing import Any

import pytest

import weave
from weave.trace import errors
from weave.trace.op import is_op, op
from weave.trace.refs import ObjectRef, parse_uri
from weave.trace.vals import MissingSelfInstanceError
from weave.trace.weave_client import Call


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
    res, call = weave_obj.method.call(weave_obj, 1)
    assert isinstance(call, Call)
    assert call.inputs == {
        "self": ObjectRef(
            entity="shawn",
            project="test-project",
            name="A",
            _digest="nzAe1JtLJFEVeEo3yX0TOYYGhh7vAOFYRentYI9ik6U",
            _extra=(),
        ),
        "a": 1,
    }
    assert call.output == 2
    assert res == 2

    weave_obj_method_ref = weave.publish(weave_obj.method)
    with pytest.raises(MissingSelfInstanceError):
        weave_obj_method2 = weave_obj_method_ref.get()

    with pytest.raises(errors.OpCallError):
        res2, call2 = py_obj.method.call(1)


@pytest.mark.asyncio
async def test_async_method(client, weave_obj, py_obj):
    assert await weave_obj.amethod(1) == 2
    assert await py_obj.amethod(1) == 2

    weave_obj_amethod_ref = weave.publish(weave_obj.amethod)
    with pytest.raises(MissingSelfInstanceError):
        weave_obj_amethod2 = weave_obj_amethod_ref.get()


@pytest.mark.asyncio
async def test_async_method_call(client, weave_obj, py_obj):
    res, call = await weave_obj.amethod.call(weave_obj, 1)
    assert isinstance(call, Call)
    assert call.inputs == {
        "self": ObjectRef(
            entity="shawn",
            project="test-project",
            name="A",
            _digest="nzAe1JtLJFEVeEo3yX0TOYYGhh7vAOFYRentYI9ik6U",
            _extra=(),
        ),
        "a": 1,
    }
    assert call.output == 2
    assert res == 2

    weave_obj_amethod_ref = weave.publish(weave_obj.amethod)
    with pytest.raises(MissingSelfInstanceError):
        weave_obj_amethod2 = weave_obj_amethod_ref.get()

    with pytest.raises(errors.OpCallError):
        res2, call2 = await py_obj.amethod.call(1)


def test_sync_func_patching_passes_inspection(func):
    assert is_op(func)
    assert inspect.isfunction(func)


def test_async_func_patching_passes_inspection(afunc):
    assert is_op(afunc)
    assert inspect.iscoroutinefunction(afunc)


def test_sync_method_patching_passes_inspection(weave_obj, py_obj):
    assert is_op(weave_obj.method)
    assert inspect.ismethod(weave_obj.method)

    assert is_op(py_obj.method)
    assert inspect.ismethod(py_obj.method)


def test_async_method_patching_passes_inspection(weave_obj, py_obj):
    assert is_op(weave_obj.amethod)
    assert inspect.iscoroutinefunction(weave_obj.amethod)
    assert inspect.ismethod(weave_obj.amethod)

    assert is_op(py_obj.amethod)
    assert inspect.iscoroutinefunction(py_obj.amethod)
    assert inspect.ismethod(py_obj.amethod)


def test_sync_method_calls(client, weave_obj):
    for x in range(3):
        weave_obj.method(x)

    for x in range(3):
        weave_obj.method.call(weave_obj, x)

    calls = weave_obj.method.calls()
    calls = list(calls)

    assert len(calls) == 6


@pytest.mark.asyncio
async def test_async_method_calls(client, weave_obj):
    for x in range(3):
        await weave_obj.amethod(x)

    for x in range(3):
        await weave_obj.amethod.call(weave_obj, x)

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
    res, call = weave_obj.method.call(weave_obj, 1)
    res2, call2 = weave_obj2.method.call(weave_obj2, 1)
    assert res == res2
    assert call.inputs == call2.inputs
    assert call.output == call2.output

    res3, call3 = await weave_obj.amethod.call(weave_obj, 1)
    res4, call4 = await weave_obj2.amethod.call(weave_obj2, 1)
    assert res3 == res4
    assert call3.inputs == call4.inputs
    assert call3.output == call4.output


def test_postprocessing_funcs(client):
    def postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
        d = {}
        for k, v in inputs.items():
            if k in {"hide_me", "and_me"}:
                continue
            d[k] = v
        return d

    def postprocess_output(output: dict[str, Any]) -> dict[str, Any]:
        d = {}
        for k, v in output.items():
            if k == "also_hide_me":
                continue
            new_k = f"postprocessed_{k}"
            d[new_k] = v
        return d

    @weave.op(
        postprocess_inputs=postprocess_inputs,
        postprocess_output=postprocess_output,
    )
    def func(a: int, hide_me: str, and_me: str) -> dict[str, Any]:
        return {"b": a + 1, "also_hide_me": "12345"}

    res = func(1, "should_be_hidden", "also_hidden")
    assert res == {"b": 2, "also_hide_me": "12345"}

    calls = list(client.calls())
    call = calls[0]

    assert call.inputs == {"a": 1}
    assert call.output == {"postprocessed_b": 2}


def test_op_call_display_name_str(client):
    @op(call_display_name="example")
    def func():
        return 1

    func()

    calls = list(client.calls())
    call = calls[0]

    assert call.display_name == "example"


def test_op_call_display_name_callable_invalid():
    with pytest.raises(ValueError, match="must take exactly 1 argument"):

        @op(call_display_name=lambda: "example")
        def func():
            return 1


def test_op_call_display_name_callable_lambda(client):
    @op(call_display_name=lambda call: f"{call.project_id}-123")
    def func():
        return 1

    func()

    calls = list(client.calls())
    call = calls[0]

    assert call.display_name == "shawn/test-project-123"


def test_op_call_display_name_callable_func(client):
    def custom_display_name_func(call) -> str:
        reversed_project = call.project_id[::-1]
        name_ascii_sum = sum(ord(c) for c in reversed_project)
        return f"wow-{name_ascii_sum}-{reversed_project}"

    @op(call_display_name=custom_display_name_func)
    def func():
        return 1

    func()

    calls = list(client.calls())
    call = calls[0]

    assert call.display_name == "wow-1844-tcejorp-tset/nwahs"


def test_op_call_display_name_callable_other_attributes(client):
    def custom_attribute_name(call):
        model = call.attributes["model"]
        revision = call.attributes["revision"]
        now = call.attributes["date"]

        return f"{model}__{revision}__{now}"

    @op(call_display_name=custom_attribute_name)
    def func():
        return 1

    with weave.attributes(
        {
            "model": "finetuned-llama-3.1-8b",
            "revision": "v0.1.2",
            "date": "2024-08-01",
        }
    ):
        func()

    with weave.attributes(
        {
            "model": "finetuned-gpt-4o",
            "revision": "v0.1.3",
            "date": "2024-08-02",
        }
    ):
        func()

    calls = list(client.calls())
    assert calls[0].display_name == "finetuned-llama-3.1-8b__v0.1.2__2024-08-01"
    assert calls[1].display_name == "finetuned-gpt-4o__v0.1.3__2024-08-02"


def test_op_call_display_name_modified_dynamically(client):
    def custom_display_name1(call):
        return "wow"

    def custom_display_name2(call):
        return "amazing"

    @weave.op(call_display_name="string")
    def func():
        return 1

    func()

    func.call_display_name = custom_display_name1
    func()

    func.call_display_name = custom_display_name2
    func()

    calls = list(client.calls())
    assert calls[0].display_name == "string"
    assert calls[1].display_name == "wow"
    assert calls[2].display_name == "amazing"


def test_op_name(client):
    @op(name="custom_name")
    def func():
        return 1

    func()

    calls = list(client.calls())
    call = calls[0]

    parsed = parse_uri(call.op_name)
    assert parsed.name == "custom_name"
