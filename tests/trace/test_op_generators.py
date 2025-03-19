from collections.abc import AsyncGenerator, Generator

import pytest

import weave


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
        async for j in await nested_async_generator(i):
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
    for i, call in enumerate(root_call.children()):
        assert "nested_generator" in call.op_name
        for j, call2 in enumerate(call.children()):
            assert "inner" in call2.op_name
            assert call2.inputs["x"] == j


@pytest.mark.asyncio
async def test_basic_async_gen(client):
    lst = []
    res = await basic_async_gen(3)
    async for i in res:
        lst.append(i)

    assert lst == [0, 1, 2]

    calls = client.get_calls()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_nested_async_generator(client):
    lst = []
    res = await nested_async_generator(3)
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
    res = await deeply_nested_async_generator(4)
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
    for i, call in enumerate(root_call.children()):
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
    res = await basic_async_gen_with_accumulator(3)

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
    res = await async_gen_with_decorator_accumulator(3)

    # The generator still works as expected
    assert [item async for item in res] == [0, 1, 2]

    # Get the call and check its output
    calls = client.get_calls()
    assert len(calls) == 1
    assert calls[0].output == [0, 1, 2]
