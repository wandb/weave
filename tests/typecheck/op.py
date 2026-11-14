"""Check preserved op signatures, including errors that must not become Any.

Run with the op-typing pre-commit hook. An unused ignore means an invalid call
was accepted, so the negative cases also catch permissive fallback overloads.
"""

from typing_extensions import assert_type

import weave


@weave.op
def bare(value: int, *, label: str) -> str:
    return label * value


@weave.op()
def factory(value: int, *, label: str) -> str:
    return label * value


@weave.op(name="configured", tracing_sample_rate=0.5)
def configured(value: int = 1, *, label: str = "ok") -> str:
    return label * value


@weave.op()
def variadic(first: int, /, *values: int, label: str = "ok", **counts: int) -> str:
    return label * (first + sum(values) + sum(counts.values()))


class Example:
    @weave.op
    def method(self, value: int, *, label: str) -> str:
        return label * value

    @weave.op()
    async def async_method(self, value: int, *, label: str) -> str:
        return label * value


@weave.op
async def async_bare(value: int, *, label: str) -> str:
    return label * value


@weave.op()
async def async_factory(value: int, *, label: str) -> str:
    return label * value


def check_sync() -> None:
    assert_type(bare(1, label="ok"), str)
    assert_type(factory(1, label="ok"), str)
    assert_type(configured(), str)
    assert_type(configured(2, label="ok"), str)
    assert_type(variadic(1, 2, 3, label="ok", extra=4), str)
    assert_type(Example().method(1, label="ok"), str)
    assert_type(Example.method(Example(), 1, label="ok"), str)
    # Runtime metadata is supported by the existing dynamic call helper.
    bare.call(1, label="ok", __weave={"display_name": "custom"})

    bare("bad", label="ok")  # type: ignore[arg-type]
    bare(1)  # type: ignore[call-arg]
    factory("bad", label="ok")  # type: ignore[arg-type]
    factory(1)  # type: ignore[call-arg]
    configured("bad")  # type: ignore[arg-type]
    configured(1, "not keyword-only")  # type: ignore[misc]
    variadic("bad")  # type: ignore[arg-type]
    variadic(1, extra="bad")  # type: ignore[arg-type]
    Example().method("bad", label="ok")  # type: ignore[arg-type]
    Example().method(1)  # type: ignore[call-arg]


async def check_async() -> None:
    assert_type(await async_bare(1, label="ok"), str)
    assert_type(await async_factory(1, label="ok"), str)
    assert_type(await Example().async_method(1, label="ok"), str)

    await async_bare("bad", label="ok")  # type: ignore[arg-type]
    await async_bare(1)  # type: ignore[call-arg]
    await async_factory("bad", label="ok")  # type: ignore[arg-type]
    await async_factory(1)  # type: ignore[call-arg]
    await Example().async_method("bad", label="ok")  # type: ignore[arg-type]
    await Example().async_method(1)  # type: ignore[call-arg]
