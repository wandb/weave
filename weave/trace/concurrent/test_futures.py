import time

import pytest

from weave.trace.concurrent.futures import FutureExecutor, defer, then


def test_defer_simple():
    executor = FutureExecutor()

    def simple_task():
        return 42

    future = executor.defer(simple_task)
    assert future.result() == 42


def test_defer_with_exception():
    executor = FutureExecutor()

    def failing_task():
        raise ValueError("Test exception")

    future = executor.defer(failing_task)
    with pytest.raises(ValueError, match="Test exception"):
        future.result()


def test_then_single_future():
    executor = FutureExecutor()

    def fetch_data():
        return [1, 2, 3, 4, 5]

    def process_data(data_list):
        return sum(data_list[0])

    future_data = executor.defer(fetch_data)
    future_result = executor.then([future_data], process_data)
    assert future_result.result() == 15


def test_then_multiple_futures():
    executor = FutureExecutor()

    def fetch_data1():
        return [1, 2, 3]

    def fetch_data2():
        return [4, 5]

    def process_multiple_data(data_list):
        return sum(sum(data) for data in data_list)

    future_data1 = executor.defer(fetch_data1)
    future_data2 = executor.defer(fetch_data2)
    future_result = executor.then([future_data1, future_data2], process_multiple_data)
    assert future_result.result() == 15


def test_then_with_exception_in_future():
    executor = FutureExecutor()

    def failing_task():
        raise ValueError("Future exception")

    def process_data(data_list):
        return data_list[0]

    future_data = executor.defer(failing_task)
    future_result = executor.then([future_data], process_data)

    with pytest.raises(ValueError, match="Future exception"):
        future_result.result()


def test_then_with_exception_in_callback():
    executor = FutureExecutor()

    def fetch_data():
        return [1, 2, 3]

    def failing_process(data_list):
        raise ValueError("Callback exception")

    future_data = executor.defer(fetch_data)
    future_result = executor.then([future_data], failing_process)

    with pytest.raises(ValueError, match="Callback exception"):
        future_result.result()


def test_concurrent_execution():
    executor = FutureExecutor()

    def slow_task(delay):
        time.sleep(delay)
        return delay

    start_time = time.time()
    futures = [executor.defer(lambda: slow_task(i)) for i in range(1, 4)]
    results = [f.result() for f in futures]
    end_time = time.time()

    assert results == [1, 2, 3]
    assert end_time - start_time < 4  # Tasks should run concurrently


def test_max_workers():
    executor = FutureExecutor(max_workers=1)

    def slow_task(delay):
        time.sleep(delay)
        return delay

    start_time = time.time()
    futures = [executor.defer(lambda: slow_task(1)) for _ in range(4)]
    results = [f.result() for f in futures]
    end_time = time.time()

    assert all(r == 1 for r in results)
    total_time = end_time - start_time
    assert 4 <= total_time  # Should take about 4 seconds with 1 worker


def test_chained_then_operations():
    executor = FutureExecutor()

    def fetch_data():
        return [1, 2, 3, 4, 5]

    def double_data(data_list):
        return [x * 2 for x in data_list[0]]

    def sum_data(data_list):
        return sum(data_list[0])

    future_data = executor.defer(fetch_data)
    future_doubled = executor.then([future_data], double_data)
    future_sum = executor.then([future_doubled], sum_data)

    assert future_sum.result() == 30


def test_global_defer_and_then():
    def simple_task():
        return 42

    def process_data(data_list):
        return data_list[0] * 2

    future = defer(simple_task)
    result_future = then([future], process_data)

    assert result_future.result() == 84


def test_empty_futures_list():
    executor = FutureExecutor()

    def process_data(data_list):
        return len(data_list)

    future_result = executor.then([], process_data)
    assert future_result.result() == 0
