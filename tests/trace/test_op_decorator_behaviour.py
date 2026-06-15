import inspect
from typing import Annotated, Any, Literal, get_type_hints

import pytest

import weave
from weave.trace.call import Call
from weave.trace.op import (
    OpCallError,
    _default_on_input_handler,
    is_op,
    op,
    setup_dunder_weave_dict,
)
from weave.trace.refs import ObjectRef, Ref
from weave.trace.vals import MissingSelfInstanceError


@pytest.fixture
def func():
    @op
    def _func(a: int) -> int:
        return a + 1

    return _func


@pytest.fixture
def afunc():
    @op
    async def _afunc(a: int) -> int:
        return a + 1

    return _afunc


@pytest.fixture
def weave_obj():
    class A(weave.Object):
        @op
        def method(self, a: int) -> int:
            return a + 1

        @op
        async def amethod(self, a: int) -> int:
            return a + 1

    return A()


@pytest.fixture
def py_obj():
    class B:
        @op
        def method(self, a: int) -> int:
            return a + 1

        @op
        async def amethod(self, a: int) -> int:
            return a + 1

    return B()


def test_sync_func(weave_active, func):
    assert func(1) == 2

    res, call = func.call(1)
    assert isinstance(call, Call)
    assert call.inputs == {"a": 1}
    assert call.output == 2
    assert res == 2

    ref = weave.publish(func)
    func2 = ref.get()

    assert func2(1) == 2
    res2, call2 = func2.call(1)
    assert isinstance(call2, Call)
    assert call2.inputs == {"a": 1}
    assert call2.output == 2
    assert res2 == 2


@pytest.mark.asyncio
async def test_async_func(weave_active, afunc):
    assert await afunc(1) == 2

    res, call = await afunc.call(1)
    assert isinstance(call, Call)
    assert call.inputs == {"a": 1}
    assert call.output == 2
    assert res == 2

    ref = weave.publish(afunc)
    afunc2 = ref.get()

    assert await afunc2(1) == 2
    res2, call2 = await afunc2.call(1)
    assert isinstance(call2, Call)
    assert call2.inputs == {"a": 1}
    assert call2.output == 2
    assert res2 == 2


def test_sync_method(weave_active, weave_obj, py_obj):
    assert weave_obj.method(1) == 2
    assert py_obj.method(1) == 2

    res, call = weave_obj.method.call(weave_obj, 1)
    assert isinstance(call, Call)
    assert call.inputs == {
        "self": ObjectRef(
            entity="shawn",
            project="test-project",
            name="A",
            _digest="dUav0vWFJzAcopRqS8sDEzbWDlyjMQD01Y8joTgfsG8",
            _extra=(),
        ),
        "a": 1,
    }
    assert call.output == 2
    assert res == 2

    weave_obj_method_ref = weave.publish(weave_obj.method)
    with pytest.raises(MissingSelfInstanceError):
        weave_obj_method2 = weave_obj_method_ref.get()

    with pytest.raises(OpCallError):
        res2, call2 = py_obj.method.call(1)


@pytest.mark.asyncio
async def test_async_method(weave_active, weave_obj, py_obj):
    assert await weave_obj.amethod(1) == 2
    assert await py_obj.amethod(1) == 2

    res, call = await weave_obj.amethod.call(weave_obj, 1)
    assert isinstance(call, Call)
    assert call.inputs == {
        "self": ObjectRef(
            entity="shawn",
            project="test-project",
            name="A",
            _digest="dUav0vWFJzAcopRqS8sDEzbWDlyjMQD01Y8joTgfsG8",
            _extra=(),
        ),
        "a": 1,
    }
    assert call.output == 2
    assert res == 2

    weave_obj_amethod_ref = weave.publish(weave_obj.amethod)
    with pytest.raises(MissingSelfInstanceError):
        weave_obj_amethod2 = weave_obj_amethod_ref.get()

    with pytest.raises(OpCallError):
        res2, call2 = await py_obj.amethod.call(1)


def test_patching_passes_inspection(func, afunc, weave_obj, py_obj):
    assert is_op(func)
    assert inspect.isfunction(func)

    assert is_op(afunc)
    assert inspect.iscoroutinefunction(afunc)

    assert is_op(weave_obj.method)
    assert inspect.ismethod(weave_obj.method)
    assert is_op(py_obj.method)
    assert inspect.ismethod(py_obj.method)

    assert is_op(weave_obj.amethod)
    assert inspect.iscoroutinefunction(weave_obj.amethod)
    assert inspect.ismethod(weave_obj.amethod)
    assert is_op(py_obj.amethod)
    assert inspect.iscoroutinefunction(py_obj.amethod)
    assert inspect.ismethod(py_obj.amethod)


def test_sync_method_calls(weave_active, weave_obj):
    for x in range(3):
        weave_obj.method(x)

    for x in range(3):
        weave_obj.method.call(weave_obj, x)

    calls = weave_obj.method.calls()
    calls = list(calls)

    assert len(calls) == 6


@pytest.mark.asyncio
async def test_async_method_calls(weave_active, weave_obj):
    for x in range(3):
        await weave_obj.amethod(x)

    for x in range(3):
        await weave_obj.amethod.call(weave_obj, x)

    calls = weave_obj.amethod.calls()
    calls = list(calls)

    assert len(calls) == 6


@pytest.mark.asyncio
async def test_gotten_object_method_is_callable(weave_active, weave_obj):
    ref = weave.publish(weave_obj)

    weave_obj2 = ref.get()
    assert weave_obj.method(1) == weave_obj2.method(1) == 2
    assert await weave_obj.amethod(1) == await weave_obj2.amethod(1) == 2


@pytest.mark.asyncio
async def test_gotten_object_method_is_callable_with_call_func(weave_active, weave_obj):
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

    calls = list(client.get_calls())
    call = calls[0]

    assert call.inputs == {"a": 1}
    assert call.output == {"postprocessed_b": 2}


def test_op_call_display_name_callable_invalid():
    with pytest.raises(ValueError, match="must take exactly 1 argument"):

        @op(call_display_name=lambda: "example")
        def func():
            return 1


def test_op_call_display_name(client):
    def reversed_project_name(call) -> str:
        reversed_project = call.project_id[::-1]
        name_ascii_sum = sum(ord(c) for c in reversed_project)
        return f"wow-{name_ascii_sum}-{reversed_project}"

    @op(call_display_name="example")
    def str_func():
        return 1

    @op(call_display_name=lambda call: f"{call.project_id}-123")
    def lambda_func():
        return 1

    @op(call_display_name=reversed_project_name)
    def func_func():
        return 1

    str_func()
    lambda_func()
    func_func()

    calls = list(client.get_calls())
    assert calls[0].display_name == "example"
    assert calls[1].display_name == "shawn/test-project-123"
    assert calls[2].display_name == "wow-1844-tcejorp-tset/nwahs"


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

    calls = list(client.get_calls())
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

    calls = list(client.get_calls())
    assert calls[0].display_name == "string"
    assert calls[1].display_name == "wow"
    assert calls[2].display_name == "amazing"


def test_op_name(client):
    @op(name="custom_name")
    def func():
        return 1

    func()

    calls = list(client.get_calls())
    call = calls[0]

    parsed = Ref.parse_uri(call.op_name)
    assert parsed.name == "custom_name"


def test_op_preserves_type_information():
    """Test that @op decorator preserves type information of the original function."""

    def typed_func(
        a: int,
        b: str,
        c: float | None,
        d: list[int],
        e: dict[str, float],
        f: tuple[str, int],
        g: bool,
    ) -> dict[str, Any]:
        """A function with type annotations."""
        return {"a": a, "b": b, "c": c, "d": d, "e": e, "f": f, "g": g}

    decorated_func = op(typed_func)

    # Check that the type hints and signatures are preserved
    assert get_type_hints(typed_func) == get_type_hints(decorated_func)
    assert inspect.signature(decorated_func) == inspect.signature(typed_func)

    values = {
        "a": 1,
        "b": "hello",
        "c": None,
        "d": [1, 2, 3],
        "e": {"a": 1.0, "b": 2.0},
        "f": ("hello", 1),
        "g": True,
    }
    # Check that the function can be called with the correct types
    assert typed_func(**values) == decorated_func(**values) == values


def test_op_cached_signature_drives_defaults_and_content_annotations(monkeypatch):
    @op
    def content_op(
        data: Annotated[bytes, weave.Content[Literal["txt"]]],
        *items: int,
        label: str = "fallback",
        **metadata: str,
    ) -> Annotated[bytes, weave.Content[Literal["txt"]]]:
        return data

    sig = inspect.signature(content_op)
    assert sig == inspect.signature(content_op.resolve_fn)
    assert sig is content_op.__signature__

    def fail_parse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("annotation parsing should be cached at decoration time")

    monkeypatch.setattr("weave.trace.op.parse_from_signature", fail_parse)
    monkeypatch.setattr("weave.trace.op.parse_content_annotation", fail_parse)

    processed = _default_on_input_handler(
        content_op, (b"hello", 1, 2), {"source": "test"}
    )

    assert processed.inputs["label"] == "fallback"
    assert processed.inputs["items"] == (1, 2)
    assert processed.inputs["metadata"] == {"source": "test"}
    assert isinstance(processed.inputs["data"], weave.Content)
    assert processed.inputs["data"].data == b"hello"
    assert processed.inputs["data"].extension == ".txt"
    assert content_op.postprocess_output is not None
    output = content_op.postprocess_output(b"hello")
    assert isinstance(output, weave.Content)
    assert output.data == b"hello"
    assert output.extension == ".txt"


def test_op_annotation_parse_failure_at_decoration_falls_back_at_runtime():
    # When `parse_from_signature` raises while decorating, the op caches
    # the `PARSE_DEFERRED` sentinel and the runtime handler retries parsing
    # both inputs and the return annotation against the live signature.
    from weave.trace.op import PARSE_DEFERRED

    def failing_parse(*args: Any, **kwargs: Any) -> Any:
        raise ValueError("simulated parse failure")

    with pytest.MonkeyPatch.context() as m:
        m.setattr("weave.trace.op.parse_from_signature", failing_parse)

        @op
        def my_op(
            data: Annotated[bytes, weave.Content[Literal["txt"]]],
        ) -> Annotated[bytes, weave.Content[Literal["txt"]]]:
            return data

    assert my_op._weave_cached_parsed_input_annotations is PARSE_DEFERRED
    assert my_op._weave_cached_parsed_return_annotation is PARSE_DEFERRED

    processed = _default_on_input_handler(my_op, (b"hello",), {})
    assert isinstance(processed.inputs["data"], weave.Content)
    assert processed.inputs["data"].data == b"hello"
    assert my_op.postprocess_output is not None
    output = my_op.postprocess_output(b"hello")
    assert isinstance(output, weave.Content)
    assert output.extension == ".txt"


def test_op_signature_failure_at_call_raises_op_call_error(monkeypatch):
    # When `inspect.signature` raises at call time (after a successful
    # decoration), the handler must wrap the failure in `OpCallError`.
    @op
    def my_op(x: int) -> int:
        return x + 1

    def failing_signature(*args: Any, **kwargs: Any) -> inspect.Signature:
        raise ValueError("runtime signature failure")

    monkeypatch.setattr("weave.trace.op.inspect.signature", failing_signature)

    with pytest.raises(OpCallError, match="runtime signature failure"):
        _default_on_input_handler(my_op, (5,), {})


@pytest.mark.parametrize(
    ("kind", "color", "expected_kind", "expected_color"),
    [
        ("tool", None, "tool", None),
        (None, "blue", None, "blue"),
        ("guardrail", None, "guardrail", None),
        ("llm", "green", "llm", "green"),
    ],
)
def test_op_kind_and_color_attributes(kind, color, expected_kind, expected_color):
    """Setting kind/color on the op decorator populates attributes.weave."""
    op_kwargs = {}
    if kind is not None:
        op_kwargs["kind"] = kind
    if color is not None:
        op_kwargs["color"] = color

    @op(**op_kwargs)
    def func(x: int) -> int:
        return x + 1

    weave_attrs = setup_dunder_weave_dict(func)["attributes"]["weave"]
    if expected_kind is None:
        assert "kind" not in weave_attrs
    else:
        assert weave_attrs["kind"] == expected_kind
    if expected_color is None:
        assert "color" not in weave_attrs
    else:
        assert weave_attrs["color"] == expected_color
