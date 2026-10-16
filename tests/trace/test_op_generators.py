import asyncio
import warnings
from collections.abc import AsyncGenerator, Generator
from contextvars import ContextVar, copy_context

import pytest

import weave
from weave.trace import op as op_module
from weave.trace.context import call_context
from weave.trace.context.call_context import get_tracing_enabled

_caller_state = ContextVar("caller_state", default="unset")


def _sampling_allowed() -> bool:
    return not get_tracing_enabled()


@pytest.fixture
def sampled_ops(monkeypatch):
    monkeypatch.setattr(op_module, "is_tracing_setting_disabled", _sampling_allowed)


@weave.op
def basic_gen(x: int) -> Generator[int, None, None]:
    yield from range(x)


@weave.op
def inner(x: int) -> int:
    return x + 1


@weave.op
def nested_generator(x: int) -> Generator[int, None, None]:
    for i in range(x):
        yield inner(i)


@weave.op
def deeply_nested_generator(x: int) -> Generator[int, None, None]:
    for i in range(x):
        yield from nested_generator(i)


@weave.op
async def basic_async_gen(x: int) -> AsyncGenerator[int, None]:
    for i in range(x):
        yield i


@weave.op
async def inner_async(x: int) -> int:
    return x + 1


@weave.op
async def nested_async_generator(x: int) -> AsyncGenerator[int, None]:
    for i in range(x):
        yield await inner_async(i)


@weave.op
async def deeply_nested_async_generator(x: int) -> AsyncGenerator[int, None]:
    for i in range(x):
        async for j in nested_async_generator(i):
            yield j


def test_basic_gen(client):
    res = basic_gen(3)
    assert list(res) == [0, 1, 2]

    calls = client.get_calls()
    assert len(calls) == 1


def test_nested_generator(client):
    res = nested_generator(3)
    assert list(res) == [1, 2, 3]

    calls = client.get_calls()
    assert len(calls) == 4

    root_call = calls[0]
    assert "nested_generator" in root_call.op_name
    for i, call in enumerate(root_call.children()):
        assert "inner" in call.op_name
        assert call.inputs["x"] == i


def test_deeply_nested_generator(client):
    res = deeply_nested_generator(4)
    # basic_gen(0) -> nothing
    # basic_gen(1) -> 1
    # basic_gen(2) -> 1, 2
    # basic_gen(3) -> 1, 2, 3
    assert list(res) == [1, 1, 2, 1, 2, 3]

    calls = client.get_calls()
    assert len(calls) == 11

    root_call = calls[0]
    assert "deeply_nested_generator" in root_call.op_name
    for _i, call in enumerate(root_call.children()):
        assert "nested_generator" in call.op_name
        for j, call2 in enumerate(call.children()):
            assert "inner" in call2.op_name
            assert call2.inputs["x"] == j


@pytest.mark.asyncio
async def test_basic_async_gen(client):
    lst = []
    res = basic_async_gen(3)
    async for i in res:
        lst.append(i)

    assert lst == [0, 1, 2]

    calls = client.get_calls()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_nested_async_generator(client):
    lst = []
    res = nested_async_generator(3)
    async for i in res:
        lst.append(i)

    assert lst == [1, 2, 3]

    calls = client.get_calls()
    assert len(calls) == 4

    root_call = calls[0]
    assert "nested_async_generator" in root_call.op_name
    for i, call in enumerate(root_call.children()):
        assert "inner_async" in call.op_name
        assert call.inputs["x"] == i


@pytest.mark.asyncio
async def test_deeply_nested_async_generator(client):
    lst = []
    res = deeply_nested_async_generator(4)
    async for i in res:
        lst.append(i)

    # basic_gen(0) -> nothing
    # basic_gen(1) -> 1
    # basic_gen(2) -> 1, 2
    # basic_gen(3) -> 1, 2, 3
    assert lst == [1, 1, 2, 1, 2, 3]

    calls = client.get_calls()
    assert len(calls) == 11

    root_call = calls[0]
    assert "deeply_nested_async_generator" in root_call.op_name
    for _, call in enumerate(root_call.children()):
        assert "nested_async_generator" in call.op_name
        for j, call2 in enumerate(call.children()):
            assert "inner_async" in call2.op_name
            assert call2.inputs["x"] == j


def list_accumulator(acc, value):
    if acc is None:
        acc = []
    acc.append(value)
    return acc


@weave.op(accumulator=list_accumulator)
def basic_gen_with_accumulator(x: int) -> Generator[int, None, None]:
    yield from range(x)


def test_generator_with_custom_accumulator(client):
    # Call the generator with the accumulator from the decorator
    res = basic_gen_with_accumulator(3)

    # The generator still works as expected
    assert list(res) == [0, 1, 2]

    # Get the call and check its output
    calls = client.get_calls()
    assert len(calls) == 1
    assert calls[0].output == [0, 1, 2]


async def async_list_accumulator(acc, val):
    if acc is None:
        acc = []
    acc.append(val)
    return acc


@weave.op(accumulator=async_list_accumulator)
async def basic_async_gen_with_accumulator(x: int) -> AsyncGenerator[int, None]:
    for i in range(x):
        yield i


@pytest.mark.asyncio
async def test_async_generator_with_custom_accumulator(client):
    # Call the generator with the accumulator from the decorator
    res = basic_async_gen_with_accumulator(3)

    # The generator still works as expected
    assert [item async for item in res] == [0, 1, 2]

    # Get the call and check its output
    calls = client.get_calls()
    assert len(calls) == 1
    assert calls[0].output == [0, 1, 2]


def test_nested_generator_multiple_iterations(client):
    """Test that nested generators work correctly when called multiple times.

    This is a regression test for a bug where the call context was being double-pushed
    for generators, causing incorrect parent-child relationships when the same
    generator was called multiple times in a loop.
    """

    @weave.op
    def inner_gen():
        yield 1

    @weave.op
    def outer_gen():
        yield from inner_gen()

    # Call outer_gen multiple times in a loop
    results = []
    for _ in range(2):
        for val in outer_gen():
            results.append(val)

    assert results == [1, 1]

    # Verify call stack is empty after all iterations
    assert call_context.get_call_stack() == []

    # Get all calls
    calls = client.get_calls()

    # Should have 4 calls total: 2 outer_gen calls, each with 1 inner_gen child
    assert len(calls) == 4

    # Find outer calls
    outer_calls = [c for c in calls if "outer_gen" in c.op_name]
    assert len(outer_calls) == 2

    # Each outer call should have no parent (they are root calls)
    for outer_call in outer_calls:
        assert outer_call.parent_id is None

    # Each outer call should have exactly one inner_gen child
    for outer_call in outer_calls:
        children = list(outer_call.children())
        assert len(children) == 1
        assert "inner_gen" in children[0].op_name


@pytest.mark.trace_server
def test_sampled_sync_generator_restores_caller_context_and_protocol(sampled_ops):
    body_states = []

    @weave.op(tracing_sample_rate=0)
    def sampled():
        body_states.append((get_tracing_enabled(), _caller_state.get()))
        received = yield 1
        body_states.append((get_tracing_enabled(), _caller_state.get(), received))
        try:
            yield 2
        finally:
            body_states.append((get_tracing_enabled(), _caller_state.get(), "cleanup"))
        return "done"  # noqa: B901

    caller_token = _caller_state.set("left")
    try:
        gen = sampled()
        assert get_tracing_enabled()
        assert next(gen) == 1
        assert get_tracing_enabled()
        assert _caller_state.get() == "left"

        _caller_state.set("right")
        assert gen.send("sent") == 2
        assert get_tracing_enabled()
        assert _caller_state.get() == "right"

        with pytest.raises(StopIteration) as stop:
            next(gen)
        assert stop.value.value == "done"
        assert get_tracing_enabled()
        assert body_states == [
            (False, "left"),
            (False, "right", "sent"),
            (False, "right", "cleanup"),
        ]
    finally:
        _caller_state.reset(caller_token)


@pytest.mark.trace_server
def test_sampled_sync_generator_throw_and_close_restore_context(sampled_ops):
    body_states = []
    caught = []

    @weave.op(tracing_sample_rate=0)
    def sampled():
        try:
            body_states.append(get_tracing_enabled())
            yield 1
        except ValueError as error:
            body_states.append(get_tracing_enabled())
            caught.append(error)
            yield 2
        finally:
            body_states.append(get_tracing_enabled())

    gen = sampled()
    assert next(gen) == 1
    injected = ValueError("bad")
    with warnings.catch_warnings(record=True) as warning_records:
        warnings.simplefilter("always", DeprecationWarning)
        assert gen.throw(injected) == 2
    assert not [
        warning
        for warning in warning_records
        if issubclass(warning.category, DeprecationWarning)
    ]
    assert caught == [injected]
    gen.close()
    assert get_tracing_enabled()
    assert body_states == [False, False, False]


@pytest.mark.trace_server
def test_sampled_sync_generator_can_resume_in_another_context(sampled_ops):
    @weave.op(tracing_sample_rate=0)
    def sampled():
        yield 1
        yield 2

    left_context = copy_context()
    right_context = copy_context()
    gen = left_context.run(sampled)
    assert left_context.run(lambda: next(gen)) == 1
    assert right_context.run(lambda: next(gen)) == 2
    assert left_context.run(get_tracing_enabled)
    assert right_context.run(get_tracing_enabled)
    with pytest.raises(StopIteration):
        right_context.run(lambda: next(gen))
    assert right_context.run(get_tracing_enabled)


@pytest.mark.trace_server
def test_sampled_sync_generator_restores_context_when_close_fails(sampled_ops):
    body_states = []

    @weave.op(tracing_sample_rate=0)
    def sampled():
        try:
            yield 1
        finally:
            body_states.append(get_tracing_enabled())
            raise RuntimeError("cleanup failed")

    gen = sampled()
    assert next(gen) == 1
    with pytest.raises(RuntimeError, match="cleanup failed"):
        gen.close()
    assert get_tracing_enabled()
    assert body_states == [False]


@pytest.mark.asyncio
@pytest.mark.trace_server
async def test_sampled_async_generator_restores_caller_context_and_nested_tracing(
    sampled_ops,
):
    body_states = []

    @weave.op
    def nested():
        body_states.append(("nested", get_tracing_enabled()))
        return 1

    @weave.op(tracing_sample_rate=0)
    async def sampled() -> AsyncGenerator[int, None]:
        body_states.append(("body", get_tracing_enabled(), _caller_state.get()))
        yield nested()
        body_states.append(("body", get_tracing_enabled(), _caller_state.get()))

    caller_token = _caller_state.set("left")
    try:
        gen = sampled()
        assert get_tracing_enabled()
        assert await anext(gen) == 1
        assert get_tracing_enabled()
        assert _caller_state.get() == "left"

        _caller_state.set("right")
        with pytest.raises(StopAsyncIteration):
            await anext(gen)
        assert get_tracing_enabled()
        assert _caller_state.get() == "right"
        assert body_states == [
            ("body", False, "left"),
            ("nested", False),
            ("body", False, "right"),
        ]
    finally:
        _caller_state.reset(caller_token)


@pytest.mark.asyncio
@pytest.mark.trace_server
async def test_sampled_async_generator_can_resume_in_another_task(sampled_ops):
    body_states = []

    @weave.op(tracing_sample_rate=0)
    async def sampled() -> AsyncGenerator[int, None]:
        try:
            body_states.append((get_tracing_enabled(), _caller_state.get()))
            yield 1
            body_states.append((get_tracing_enabled(), _caller_state.get()))
            yield 2
        finally:
            body_states.append((get_tracing_enabled(), _caller_state.get(), "cleanup"))

    gen = sampled()
    task_states = []

    async def advance(label: str) -> int | None:
        caller_token = _caller_state.set(label)
        try:
            before = get_tracing_enabled()
            try:
                value = await anext(gen)
            except StopAsyncIteration:
                value = None
            task_states.append((label, before, get_tracing_enabled()))
            return value
        finally:
            _caller_state.reset(caller_token)

    first_task = asyncio.create_task(advance("left"))
    assert await first_task == 1
    second_task = asyncio.create_task(advance("right"))
    assert await second_task == 2
    exhaustion_task = asyncio.create_task(advance("exhaustion"))
    assert await exhaustion_task is None
    assert get_tracing_enabled()
    assert task_states == [
        ("left", True, True),
        ("right", True, True),
        ("exhaustion", True, True),
    ]
    assert body_states == [
        (False, "left"),
        (False, "right"),
        (False, "exhaustion", "cleanup"),
    ]


@pytest.mark.asyncio
@pytest.mark.trace_server
async def test_sampled_async_generator_error_restores_caller_context(sampled_ops):
    @weave.op(tracing_sample_rate=0)
    async def sampled() -> AsyncGenerator[int, None]:
        yield 1
        raise ValueError("bad")

    gen = sampled()
    assert await anext(gen) == 1
    with pytest.raises(ValueError, match="bad"):
        await anext(gen)
    assert get_tracing_enabled()


@pytest.mark.asyncio
@pytest.mark.trace_server
async def test_sampled_async_generator_close_and_cancellation_cleanup(sampled_ops):
    cleanup = []
    underlying_started = asyncio.Event()
    release_underlying = asyncio.Event()

    @weave.op(tracing_sample_rate=0)
    async def sampled() -> AsyncGenerator[int, None]:
        try:
            yield 1
            underlying_started.set()
            await release_underlying.wait()
        finally:
            cleanup.append((get_tracing_enabled(), _caller_state.get()))

    caller_token = _caller_state.set("close")
    try:
        gen = sampled()
        assert await anext(gen) == 1
        await gen.aclose()
        assert get_tracing_enabled()
        assert _caller_state.get() == "close"
    finally:
        _caller_state.reset(caller_token)
    assert cleanup == [(False, "close")]
    assert get_tracing_enabled()

    consumer_states = []

    async def consume() -> None:
        caller_token = _caller_state.set("cancel")
        try:
            async for _ in sampled():
                await asyncio.sleep(0)
        finally:
            consumer_states.append((get_tracing_enabled(), _caller_state.get()))
            _caller_state.reset(caller_token)

    task = asyncio.create_task(consume())
    await underlying_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert get_tracing_enabled()
    assert consumer_states == [(True, "cancel")]
    assert cleanup == [(False, "close"), (False, "cancel")]


@pytest.mark.asyncio
async def test_nested_async_generator_multiple_iterations(client):
    """Test that nested async generators work correctly when called multiple times.

    This is a regression test for a bug where the call context was being double-pushed
    for generators, causing incorrect parent-child relationships when the same
    generator was called multiple times in a loop.
    """

    @weave.op
    async def inner_gen():
        yield 1

    @weave.op
    async def outer_gen():
        async for x in inner_gen():
            yield x

    # Call outer_gen multiple times in a loop
    results = []
    for _ in range(2):
        async for val in outer_gen():
            results.append(val)

    assert results == [1, 1]

    # Verify call stack is empty after all iterations
    assert call_context.get_call_stack() == []

    # Get all calls
    calls = client.get_calls()

    # Should have 4 calls total: 2 outer_gen calls, each with 1 inner_gen child
    assert len(calls) == 4

    # Find outer calls
    outer_calls = [c for c in calls if "outer_gen" in c.op_name]
    assert len(outer_calls) == 2

    # Each outer call should have no parent (they are root calls)
    for outer_call in outer_calls:
        assert outer_call.parent_id is None

    # Each outer call should have exactly one inner_gen child
    for outer_call in outer_calls:
        children = list(outer_call.children())
        assert len(children) == 1
        assert "inner_gen" in children[0].op_name
