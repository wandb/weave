import time
from concurrent.futures import Future
from typing import Any, List

import pytest

from weave.trace.concurrent.futures import FutureExecutor, defer, then


def test_defer_simple() -> None:
    executor: FutureExecutor = FutureExecutor()

    def simple_task() -> int:
        return 42

    future: Future[int] = executor.defer(simple_task)
    assert future.result() == 42


def test_defer_with_exception() -> None:
    executor: FutureExecutor = FutureExecutor()

    def failing_task() -> None:
        raise ValueError("Test exception")

    future: Future[None] = executor.defer(failing_task)
    with pytest.raises(ValueError, match="Test exception"):
        future.result()


def test_then_single_future() -> None:
    executor: FutureExecutor = FutureExecutor()

    def fetch_data() -> List[int]:
        return [1, 2, 3, 4, 5]

    def process_data(data_list: List[List[int]]) -> int:
        return sum(data_list[0])

    future_data: Future[List[int]] = executor.defer(fetch_data)
    future_result: Future[int] = executor.then([future_data], process_data)
    assert future_result.result() == 15


def test_then_multiple_futures() -> None:
    executor: FutureExecutor = FutureExecutor()

    def fetch_data1() -> List[int]:
        return [1, 2, 3]

    def fetch_data2() -> List[int]:
        return [4, 5]

    def process_multiple_data(data_list: List[List[int]]) -> int:
        return sum(sum(data) for data in data_list)

    future_data1: Future[List[int]] = executor.defer(fetch_data1)
    future_data2: Future[List[int]] = executor.defer(fetch_data2)
    future_result: Future[int] = executor.then(
        [future_data1, future_data2], process_multiple_data
    )
    assert future_result.result() == 15


def test_then_with_exception_in_future() -> None:
    executor: FutureExecutor = FutureExecutor()

    def failing_task() -> None:
        raise ValueError("Future exception")

    def process_data(data_list: List[Any]) -> Any:
        return data_list[0]

    future_data: Future[None] = executor.defer(failing_task)
    future_result: Future[Any] = executor.then([future_data], process_data)

    with pytest.raises(ValueError, match="Future exception"):
        future_result.result()


def test_then_with_exception_in_callback() -> None:
    executor: FutureExecutor = FutureExecutor()

    def fetch_data() -> List[int]:
        return [1, 2, 3]

    def failing_process(data_list: List[List[int]]) -> None:
        raise ValueError("Callback exception")

    future_data: Future[List[int]] = executor.defer(fetch_data)
    future_result: Future[None] = executor.then([future_data], failing_process)

    with pytest.raises(ValueError, match="Callback exception"):
        future_result.result()


def test_concurrent_execution() -> None:
    executor: FutureExecutor = FutureExecutor()

    def slow_task(delay: int) -> int:
        time.sleep(delay)
        return delay

    start_time: float = time.time()
    futures: List[Future[int]] = [
        executor.defer(lambda: slow_task(i)) for i in range(1, 4)
    ]
    results: List[int] = [f.result() for f in futures]
    end_time: float = time.time()

    assert results == [1, 2, 3]
    assert end_time - start_time < 4  # Tasks should run concurrently


def test_max_workers() -> None:
    executor: FutureExecutor = FutureExecutor(max_workers=1)

    def slow_task(delay: int) -> int:
        time.sleep(delay)
        return delay

    start_time: float = time.time()
    futures: List[Future[int]] = [
        executor.defer(lambda: slow_task(1)) for _ in range(4)
    ]
    results: List[int] = [f.result() for f in futures]
    end_time: float = time.time()

    assert all(r == 1 for r in results)
    total_time: float = end_time - start_time
    assert 4 <= total_time  # Should take about 4 seconds with 1 worker


def test_chained_then_operations() -> None:
    executor: FutureExecutor = FutureExecutor()

    def fetch_data() -> List[int]:
        return [1, 2, 3, 4, 5]

    def double_data(data_list: List[List[int]]) -> List[int]:
        return [x * 2 for x in data_list[0]]

    def sum_data(data_list: List[List[int]]) -> int:
        return sum(data_list[0])

    future_data: Future[List[int]] = executor.defer(fetch_data)
    future_doubled: Future[List[int]] = executor.then([future_data], double_data)
    future_sum: Future[int] = executor.then([future_doubled], sum_data)

    assert future_sum.result() == 30


def test_global_defer_and_then() -> None:
    def simple_task() -> int:
        return 42

    def process_data(data_list: List[int]) -> int:
        return data_list[0] * 2

    future: Future[int] = defer(simple_task)
    result_future: Future[int] = then([future], process_data)

    assert result_future.result() == 84


def test_empty_futures_list() -> None:
    executor: FutureExecutor = FutureExecutor()

    def process_data(data_list: List[Any]) -> int:
        return len(data_list)

    future_result: Future[int] = executor.then([], process_data)
    assert future_result.result() == 0
