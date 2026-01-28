from collections.abc import AsyncGenerator, Generator

import pytest

import weave
from weave.trace.context import call_context


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


@weave.op(accumulator=list_accumulator)
def gen_with_decorator_accumulator(x: int) -> Generator[int, None, None]:
    yield from range(x)


def test_generator_with_decorator_accumulator(client):
    # Call the generator with the accumulator from the decorator
    res = gen_with_decorator_accumulator(3)

    # The generator still works as expected
    assert list(res) == [0, 1, 2]

    # Get the call and check its output
    calls = client.get_calls()
    assert len(calls) == 1
    assert calls[0].output == [0, 1, 2]


@weave.op(accumulator=async_list_accumulator)
async def async_gen_with_decorator_accumulator(x: int) -> AsyncGenerator[int, None]:
    for i in range(x):
        yield i


@pytest.mark.asyncio
async def test_async_generator_with_decorator_accumulator(client):
    # Call the generator with the accumulator from the decorator
    res = async_gen_with_decorator_accumulator(3)

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
