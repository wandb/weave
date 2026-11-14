"""Runtime compatibility for the statically preserved op call signatures."""

import inspect

import pytest

import weave
from weave.trace.context import weave_client_context


@pytest.mark.parametrize(
    "decorate", [weave.op, weave.op(), weave.op(name="configured")]
)
def test_op_signature_runtime(decorate):
    def original(first: int, /, *values: int, label: str = "ok", **counts: int) -> str:
        return label * (first + sum(values) + sum(counts.values()))

    decorated = decorate(original)
    assert inspect.signature(decorated) == inspect.signature(original)
    assert decorated(1) == "ok"
    assert decorated(1, 2, label="x", extra=3) == "xxxxxx"
    # The type-only protocol change must not forward metadata to the function.
    assert weave_client_context.get_weave_client() is None
    assert decorated(1, __weave={"display_name": "custom"}) == "ok"
    result, _ = decorated.call(1, __weave={"display_name": "custom"})
    assert result == "ok"


@pytest.mark.asyncio
async def test_op_bound_and_async_signatures_runtime():
    class Example:
        @weave.op
        def method(self, value: int, *, label: str = "ok") -> str:
            return label * value

        @weave.op()
        async def async_method(self, value: int, *, label: str = "ok") -> str:
            return label * value

    @weave.op
    async def bare(value: int, *, label: str = "ok") -> str:
        return label * value

    @weave.op()
    async def factory(value: int, *, label: str = "ok") -> str:
        return label * value

    instance = Example()
    assert instance.method(2) == "okok"
    assert Example.method(instance, 2, label="x") == "xx"
    assert await instance.async_method(2) == "okok"
    assert await bare(2) == "okok"
    assert await factory(2, label="x") == "xx"
    assert await factory(1, __weave={"display_name": "custom"}) == "ok"
    result, _ = await factory.call(1, __weave={"display_name": "custom"})
    assert result == "ok"
