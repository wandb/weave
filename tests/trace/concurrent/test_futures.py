import threading
import time
from concurrent.futures import Future
from typing import Any

import pytest

from weave.trace.concurrent.futures import FutureExecutor

# Wait budget for events/threads in flush race tests; generous so slow CI
# runners don't false-fail, tight enough that a real hang surfaces fast.
EVENT_TIMEOUT_S = 5
# Window we let an incorrect flush() implementation use to (wrongly) return
# before chained callback work completes. Long enough to observe the bug,
# short enough to keep the suite snappy.
RACE_WINDOW_S = 0.05


def test_defer_simple() -> None:
    executor: FutureExecutor = FutureExecutor()

    def simple_task() -> int:
        return 42

    future: Future[int] = executor.defer(simple_task)
    assert future.result() == 42


@pytest.mark.disable_logging_error_check
def test_defer_with_exception(log_collector) -> None:
    executor: FutureExecutor = FutureExecutor()

    def failing_task() -> None:
        raise ValueError("Test exception")

    future: Future[None] = executor.defer(failing_task)
    with pytest.raises(ValueError, match="Test exception"):
        future.result()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert "ValueError: Test exception" in logs[0].getMessage()


def test_then_single_future() -> None:
    executor: FutureExecutor = FutureExecutor()

    def fetch_data() -> list[int]:
        return [1, 2, 3, 4, 5]

    def process_data(data_list: list[list[int]]) -> int:
        return sum(data_list[0])

    future_data: Future[list[int]] = executor.defer(fetch_data)
    future_result: Future[int] = executor.then([future_data], process_data)
    assert future_result.result() == 15


def test_then_multiple_futures() -> None:
    executor: FutureExecutor = FutureExecutor()

    def fetch_data1() -> list[int]:
        return [1, 2, 3]

    def fetch_data2() -> list[int]:
        return [4, 5]

    def process_multiple_data(data_list: list[list[int]]) -> int:
        return sum(sum(data) for data in data_list)

    future_data1: Future[list[int]] = executor.defer(fetch_data1)
    future_data2: Future[list[int]] = executor.defer(fetch_data2)
    future_result: Future[int] = executor.then(
        [future_data1, future_data2], process_multiple_data
    )
    assert future_result.result() == 15


def test_then_multiple_futures_ordering() -> None:
    executor: FutureExecutor = FutureExecutor()

    def fetch_data1() -> list[int]:
        time.sleep(5)
        return [1, 2, 3]

    def fetch_data2() -> list[int]:
        return [4, 5]

    def process_multiple_data(data_list: list[list[int]]) -> int:
        final = []
        for data in data_list:
            final.extend(data)
        return final

    future_data2: Future[list[int]] = executor.defer(fetch_data2)
    future_data1: Future[list[int]] = executor.defer(fetch_data1)
    future_result: Future[list[int]] = executor.then(
        [future_data1, future_data2], process_multiple_data
    )

    assert future_result.result() == [1, 2, 3, 4, 5]


def test_then_multiple_futures_duplicate() -> None:
    executor: FutureExecutor = FutureExecutor()

    def fetch_data1() -> list[int]:
        return [1, 2, 3]

    def process_multiple_data(data_list: list[list[int]]) -> int:
        final = []
        for data in data_list:
            final.extend(data)
        return final

    future_data1: Future[list[int]] = executor.defer(fetch_data1)
    future_result: Future[list[int]] = executor.then(
        [future_data1, future_data1], process_multiple_data
    )

    assert future_result.result() == [1, 2, 3, 1, 2, 3]


@pytest.mark.disable_logging_error_check
def test_then_with_exception_in_future(log_collector) -> None:
    executor: FutureExecutor = FutureExecutor()

    def failing_task() -> None:
        raise ValueError("Future exception")

    def process_data(data_list: list[Any]) -> Any:
        return data_list[0]

    future_data: Future[None] = executor.defer(failing_task)
    future_result: Future[Any] = executor.then([future_data], process_data)

    with pytest.raises(ValueError, match="Future exception"):
        future_result.result()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert "ValueError: Future exception" in logs[0].getMessage()


@pytest.mark.disable_logging_error_check
def test_then_with_exception_in_callback(log_collector) -> None:
    executor: FutureExecutor = FutureExecutor()

    def fetch_data() -> list[int]:
        return [1, 2, 3]

    def failing_process(data_list: list[list[int]]) -> None:
        raise ValueError("Callback exception")

    future_data: Future[list[int]] = executor.defer(fetch_data)
    future_result: Future[None] = executor.then([future_data], failing_process)

    with pytest.raises(ValueError, match="Callback exception"):
        future_result.result()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert "ValueError: Callback exception" in logs[0].getMessage()


def test_concurrent_execution() -> None:
    executor: FutureExecutor = FutureExecutor()

    def slow_task(delay: int) -> int:
        time.sleep(delay)
        return delay

    start_time: float = time.time()
    futures: list[Future[int]] = [
        executor.defer(lambda: slow_task(i))  # noqa: B023
        for i in range(1, 4)
    ]
    results: list[int] = [f.result() for f in futures]
    end_time: float = time.time()

    assert results == [1, 2, 3]
    assert end_time - start_time < 4  # Tasks should run concurrently


def test_max_workers() -> None:
    executor: FutureExecutor = FutureExecutor(max_workers=1)

    def slow_task(delay: int) -> int:
        time.sleep(delay)
        return delay

    start_time: float = time.time()
    futures: list[Future[int]] = [
        executor.defer(lambda: slow_task(1)) for _ in range(4)
    ]
    results: list[int] = [f.result() for f in futures]
    end_time: float = time.time()

    assert all(r == 1 for r in results)
    total_time: float = end_time - start_time
    assert 4 <= total_time  # Should take about 4 seconds with 1 worker


def test_chained_then_operations() -> None:
    executor: FutureExecutor = FutureExecutor()

    def fetch_data() -> list[int]:
        return [1, 2, 3, 4, 5]

    def double_data(data_list: list[list[int]]) -> list[int]:
        return [x * 2 for x in data_list[0]]

    def sum_data(data_list: list[list[int]]) -> int:
        return sum(data_list[0])

    future_data: Future[list[int]] = executor.defer(fetch_data)
    future_doubled: Future[list[int]] = executor.then([future_data], double_data)
    future_sum: Future[int] = executor.then([future_doubled], sum_data)

    assert future_sum.result() == 30


def test_defer_and_then() -> None:
    executor: FutureExecutor = FutureExecutor()

    def simple_task() -> int:
        return 42

    def process_data(data_list: list[int]) -> int:
        return data_list[0] * 2

    future: Future[int] = executor.defer(simple_task)
    result_future: Future[int] = executor.then([future], process_data)

    assert result_future.result() == 84


def test_empty_futures_list() -> None:
    executor: FutureExecutor = FutureExecutor()

    def process_data(data_list: list[Any]) -> int:
        return len(data_list)

    future_result: Future[int] = executor.then([], process_data)
    assert future_result.result() == 0


def test_flush_waits_for_then_callback_work() -> None:
    executor: FutureExecutor = FutureExecutor(max_workers=1)
    release_root = threading.Event()
    callback_started = threading.Event()
    release_callback = threading.Event()
    flush_finished = threading.Event()

    def root_task() -> int:
        assert release_root.wait(timeout=EVENT_TIMEOUT_S)
        return 1

    def blocking_callback(data_list: list[int]) -> int:
        callback_started.set()
        assert release_callback.wait(timeout=EVENT_TIMEOUT_S)
        return data_list[0] + 1

    root_future: Future[int] = executor.defer(root_task)
    result_future: Future[int] = executor.then([root_future], blocking_callback)

    release_root.set()
    assert callback_started.wait(timeout=EVENT_TIMEOUT_S)
    # The logical then-future remains tracked while callback work is running.
    assert executor.num_outstanding_futures == 1

    flush_thread = threading.Thread(
        target=lambda: (executor.flush(), flush_finished.set())
    )
    flush_thread.start()

    try:
        time.sleep(RACE_WINDOW_S)
        early_finished = flush_finished.is_set()
    finally:
        release_callback.set()
        flush_thread.join(timeout=EVENT_TIMEOUT_S)

    assert not early_finished
    assert flush_finished.is_set()
    assert result_future.result() == 2


def test_then_callback_runs_once_under_concurrent_input_completion() -> None:
    """Two inputs completing simultaneously must not double-submit `g`.

    Both `on_done_callback` invocations can observe `all(fut.done())` as True
    in the racy interleaving; the dedup lock is what keeps `g` running once.
    """
    executor: FutureExecutor = FutureExecutor(max_workers=2)
    callback_count = 0
    count_lock = threading.Lock()

    def count_callback(data_list: list[int]) -> int:
        nonlocal callback_count
        with count_lock:
            callback_count += 1
        return sum(data_list)

    f1: Future[int] = Future()
    f2: Future[int] = Future()
    result_future: Future[int] = executor.then([f1, f2], count_callback)

    barrier = threading.Barrier(2)

    def fire(f: Future[int], v: int) -> None:
        barrier.wait(timeout=EVENT_TIMEOUT_S)
        f.set_result(v)

    threads = [
        threading.Thread(target=fire, args=(f1, 1)),
        threading.Thread(target=fire, args=(f2, 2)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=EVENT_TIMEOUT_S)

    assert result_future.result(timeout=EVENT_TIMEOUT_S) == 3
    assert executor.flush(timeout=EVENT_TIMEOUT_S)
    assert callback_count == 1


def test_flush_drains_work_added_after_snapshot() -> None:
    """Work submitted after flush() snapshots must still be drained.

    flush() snapshots `_active_futures`, waits, then re-checks. A submission
    that lands between the snapshot and the original future completing is
    the canonical case: a single-pass flush would return early and leave
    real work pending.
    """
    executor: FutureExecutor = FutureExecutor(max_workers=2)
    release_root = threading.Event()
    release_chained = threading.Event()
    chained_started = threading.Event()
    chained_finished = threading.Event()
    flush_finished = threading.Event()

    def root_task() -> int:
        assert release_root.wait(timeout=EVENT_TIMEOUT_S)
        return 1

    def chained_task() -> int:
        chained_started.set()
        assert release_chained.wait(timeout=EVENT_TIMEOUT_S)
        chained_finished.set()
        return 99

    executor.defer(root_task)

    flush_thread = threading.Thread(
        target=lambda: (executor.flush(), flush_finished.set())
    )
    flush_thread.start()

    # Let flush() snapshot _active_futures = {root_future} before the
    # chained work exists.
    time.sleep(RACE_WINDOW_S)
    # Submit additional work *after* the snapshot. This future is tracked
    # but invisible to flush()'s in-flight `as_completed` call.
    executor.defer(chained_task)
    assert chained_started.wait(timeout=EVENT_TIMEOUT_S)
    # Release root_task so the snapshot drains; flush() must outer-loop to
    # discover chained_task_future.
    release_root.set()
    # Give a single-pass flush() enough headroom to (incorrectly) return
    # after the snapshot drains but before chained_task_future completes.
    time.sleep(RACE_WINDOW_S)
    early_finished = flush_finished.is_set()

    release_chained.set()
    flush_thread.join(timeout=EVENT_TIMEOUT_S)

    assert not early_finished
    assert chained_finished.is_set()
    assert flush_finished.is_set()


def test_nested_futures_with_1_max_worker_classic_deadlock_case() -> None:
    executor: FutureExecutor = FutureExecutor(max_workers=1)

    def inner_0() -> list[int]:
        return [0]

    def inner_1() -> list[int]:
        return executor.defer(inner_0).result() + [1]

    def inner_2() -> list[int]:
        return executor.defer(inner_1).result() + [2]

    res = executor.defer(inner_2).result()
    assert res == [0, 1, 2]


def test_nested_futures_with_0_max_workers_direct() -> None:
    executor: FutureExecutor = FutureExecutor(max_workers=0)
    assert executor._executor is None

    def inner_0() -> list[int]:
        return [0]

    def inner_1() -> list[int]:
        return executor.defer(inner_0).result() + [1]

    def inner_2() -> list[int]:
        return executor.defer(inner_1).result() + [2]

    res = executor.defer(inner_2).result()
    assert executor._executor is None
    assert res == [0, 1, 2]
