import asyncio

import pytest

from weave.flow.util import async_foreach


@pytest.mark.asyncio
async def test_async_foreach_basic():
    """Test basic functionality of async_foreach."""
    input_data = range(5)
    results = []

    async def process(x: int) -> int:
        await asyncio.sleep(0.1)  # Simulate async work
        return x * 2

    async for item, result in async_foreach(
        input_data, process, max_concurrent_tasks=2
    ):
        results.append((item, result))

    assert len(results) == 5
    assert all(result == item * 2 for item, result in results)
    assert [item for item, _ in results] == list(range(5))


@pytest.mark.asyncio
async def test_async_foreach_concurrency():
    """Test that max_concurrent_tasks is respected."""
    currently_running = 0
    max_running = 0
    input_data = range(10)

    async def process(x: int) -> int:
        nonlocal currently_running, max_running
        currently_running += 1
        max_running = max(max_running, currently_running)
        await asyncio.sleep(0.1)  # Simulate async work
        currently_running -= 1
        return x

    max_concurrent = 3
    async for _, _ in async_foreach(
        input_data, process, max_concurrent_tasks=max_concurrent
    ):
        pass

    assert max_running == max_concurrent


@pytest.mark.asyncio
async def test_async_foreach_lazy_loading():
    """Test that items are loaded lazily from the iterator."""
    items_loaded = 0

    def lazy_range(n: int):
        nonlocal items_loaded
        for i in range(n):
            items_loaded += 1
            yield i

    async def process(x: int) -> int:
        await asyncio.sleep(0.1)
        return x

    # Process first 3 items then break
    async for _, _ in async_foreach(lazy_range(100), process, max_concurrent_tasks=2):
        if items_loaded >= 3:
            break

    # Should have loaded at most 4 items (3 + 1 for concurrency)
    assert items_loaded <= 4


@pytest.mark.asyncio
async def test_async_foreach_error_handling():
    """Test error handling in async_foreach."""
    input_data = range(5)

    async def process(x: int) -> int:
        if x == 3:
            raise ValueError("Test error")
        return x

    with pytest.raises(ValueError, match="Test error"):
        async for _, _ in async_foreach(input_data, process, max_concurrent_tasks=2):
            pass


@pytest.mark.asyncio
async def test_async_foreach_empty_input():
    """Test behavior with empty input sequence."""
    results = []

    async def process(x: int) -> int:
        return x

    async for item, result in async_foreach([], process, max_concurrent_tasks=2):
        results.append((item, result))

    assert len(results) == 0


@pytest.mark.asyncio
async def test_async_foreach_cancellation():
    """Test that tasks are properly cleaned up on cancellation."""
    input_data = range(100)
    results = []

    async def slow_process(x: int) -> int:
        await asyncio.sleep(0.5)  # Longer delay to ensure tasks are running
        return x

    # Create a task we can cancel
    async def run_foreach():
        async for item, result in async_foreach(
            input_data, slow_process, max_concurrent_tasks=3
        ):
            results.append((item, result))
            if len(results) >= 2:  # Cancel after 2 results
                raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await run_foreach()

    # Give a moment for any lingering tasks to complete if cleanup failed
    await asyncio.sleep(0.1)

    # Check that we got the expected number of results before cancellation
    assert len(results) == 2


@pytest.mark.asyncio
async def test_async_foreach_execution_order():
    """Test that results are yielded in input sequence order regardless of completion order."""
    # Create input data with deliberately varying processing times
    input_data = [(0, 0.3), (1, 0.1), (2, 0.2)]  # (value, delay) pairs
    calls = []
    results = []

    async def process(item: tuple[int, float]) -> int:
        calls.append(item)
        value, delay = item
        await asyncio.sleep(delay)  # Different delays to force out-of-order completion
        return value * 2

    async for item, result in async_foreach(
        input_data, process, max_concurrent_tasks=3
    ):
        results.append((item[0], result))  # Store (original_value, processed_result)

    # Verify results are in original sequence order
    assert results == [(0, 0), (1, 2), (2, 4)]
    assert calls == [(0, 0.3), (1, 0.1), (2, 0.2)]
