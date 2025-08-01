import logging
import os
import time
import timeit
from unittest import mock

import pytest
import tenacity

import weave
from tests.trace.util import capture_output, flushing_callback
from weave.trace.constants import TRACE_CALL_EMOJI
from weave.trace.settings import UserSettings, parse_and_apply_settings
from weave.trace.weave_client import get_parallelism_settings
from weave.utils.retry import with_retry


@weave.op
def func():
    return 1


def test_disabled_setting(client):
    parse_and_apply_settings(UserSettings(disabled=True))
    disabled_time = timeit.timeit(func, number=10)
    calls = list(client.get_calls())
    assert len(calls) == 0

    parse_and_apply_settings(UserSettings(disabled=False))
    enabled_time = timeit.timeit(func, number=10)
    calls = list(client.get_calls())
    assert len(calls) == 10

    assert disabled_time * 10 < enabled_time, (
        "Disabled weave should be faster than enabled weave"
    )


def test_disabled_env(client):
    os.environ["WEAVE_DISABLED"] = "true"
    disabled_time = timeit.timeit(func, number=10)
    calls = list(client.get_calls())
    assert len(calls) == 0

    os.environ["WEAVE_DISABLED"] = "false"
    enabled_time = timeit.timeit(func, number=10)
    calls = list(client.get_calls())
    assert len(calls) == 10

    assert disabled_time * 10 < enabled_time, (
        "Disabled weave should be faster than enabled weave"
    )


def test_print_call_link_setting(client_creator):
    with client_creator(settings=UserSettings(print_call_link=False)) as client:
        callbacks = [flushing_callback(client)]
        with capture_output(callbacks) as captured:
            func()
    assert TRACE_CALL_EMOJI not in captured.getvalue()

    with client_creator(settings=UserSettings(print_call_link=True)) as client:
        callbacks = [flushing_callback(client)]
        with capture_output(callbacks) as captured:
            func()
    assert TRACE_CALL_EMOJI in captured.getvalue()


def test_print_call_link_env(client):
    os.environ["WEAVE_PRINT_CALL_LINK"] = "false"
    callbacks = [flushing_callback(client)]
    with capture_output(callbacks) as captured:
        func()

    assert TRACE_CALL_EMOJI not in captured.getvalue()

    os.environ["WEAVE_PRINT_CALL_LINK"] = "true"
    callbacks = [flushing_callback(client)]
    with capture_output(callbacks) as captured:
        func()

    assert TRACE_CALL_EMOJI in captured.getvalue()

    # Clean up after test
    del os.environ["WEAVE_PRINT_CALL_LINK"]


def test_should_capture_code_setting(client):
    parse_and_apply_settings(UserSettings(capture_code=False))

    @weave.op
    def test_func():
        return 1

    ref = weave.publish(test_func)
    test_func2 = ref.get()
    code2 = test_func2.get_captured_code()
    assert "Code-capture was disabled" in code2

    parse_and_apply_settings(UserSettings(capture_code=True))

    # TODO: Not safe to change capture_code setting mid-script because the op's ref
    # does not know about the setting change.
    @weave.op
    def test_func():
        return 1

    ref2 = weave.publish(test_func)
    test_func3 = ref2.get()
    code3 = test_func3.get_captured_code()
    assert "Code-capture was disabled" not in code3


def test_should_capture_code_env(client):
    os.environ["WEAVE_CAPTURE_CODE"] = "false"

    @weave.op
    def test_func():
        return 1

    ref = weave.publish(test_func)
    test_func2 = ref.get()
    code2 = test_func2.get_captured_code()
    assert "Code-capture was disabled" in code2

    os.environ["WEAVE_CAPTURE_CODE"] = "true"

    @weave.op
    def test_func():
        return 1

    ref2 = weave.publish(test_func)
    test_func3 = ref2.get()
    code3 = test_func3.get_captured_code()
    assert "Code-capture was disabled" not in code3


def slow_operation():
    time.sleep(0.1)


def speed_test(client, count=5):
    start = time.time()
    futs = [client.future_executor.defer(slow_operation) for _ in range(count)]
    queue_time = time.time()
    for fut in futs:
        fut.result()
    end = time.time()

    queue_time_s = queue_time - start
    wait_time_s = end - queue_time
    return wait_time_s, queue_time_s


def test_client_parallelism_setting(client_creator):
    with mock.patch("os.cpu_count", return_value=4):
        with client_creator() as client:
            assert client.future_executor._max_workers == 4
            assert client.future_executor._executor._max_workers == 4

    parse_and_apply_settings(UserSettings(client_parallelism=1))
    with mock.patch("os.cpu_count", return_value=4):
        with client_creator() as client:
            assert client.future_executor._max_workers == 1
            assert client.future_executor._executor._max_workers == 1
            wait_time_1, queue_time_1 = speed_test(client)

    parse_and_apply_settings(UserSettings(client_parallelism=10))
    with client_creator() as client:
        assert client.future_executor._max_workers == 5
        assert client.future_executor._executor._max_workers == 5
        assert client.future_executor_fastlane._max_workers == 5
        wait_time_10, queue_time_10 = speed_test(client)

    # Assert that the queue time is about the same for 10 and 1
    assert queue_time_1 == pytest.approx(queue_time_10, abs=0.5)
    # Assert that the wait time is much less for 10 than 1
    assert wait_time_1 > wait_time_10

    # Test explicit None
    parse_and_apply_settings(UserSettings(client_parallelism=None))
    with mock.patch("os.cpu_count", return_value=4):
        with client_creator() as client:
            assert client.future_executor._max_workers == 4
            assert client.future_executor._executor._max_workers > 0


def test_get_parallelism_settings() -> None:
    # Test default behavior with 4 CPU cores
    with mock.patch("os.cpu_count", return_value=4):
        main, upload = get_parallelism_settings()
        assert main == 4
        assert upload == 4

    # Test explicit total parallelism override
    with mock.patch.dict(os.environ, {"WEAVE_CLIENT_PARALLELISM": "10"}):
        main, upload = get_parallelism_settings()
        assert main == 5
        assert upload == 5

    # Test disabling parallelism
    with mock.patch.dict(os.environ, {"WEAVE_CLIENT_PARALLELISM": "0"}):
        main, upload = get_parallelism_settings()
        assert main == 0
        assert upload == 0

    # Test max cap with many cores
    with mock.patch("os.cpu_count", return_value=64):
        main, upload = get_parallelism_settings()
        assert main == 16
        assert upload == 16

    # Test single core system
    with mock.patch("os.cpu_count", return_value=1):
        main, upload = get_parallelism_settings()
        assert main == 2
        assert upload == 3

    # Test when cpu_count returns None
    with mock.patch("os.cpu_count", return_value=None):
        main, upload = get_parallelism_settings()
        assert main == 2
        assert upload == 3


def test_retry_max_attempts_settings(client_creator, caplog) -> None:
    caplog.set_level(logging.INFO, logger="weave.utils.retry")

    @with_retry
    def func():
        raise RuntimeError("Test error")

    with client_creator(settings=UserSettings(retry_max_attempts=2)) as client:
        with pytest.raises(RuntimeError):
            func()

    retry_attempt_logs = [r for r in caplog.records if r.msg == "retry_attempt"]
    retry_failed_logs = [r for r in caplog.records if r.msg == "retry_failed"]

    assert len(retry_attempt_logs) == 1
    attempt_log = retry_attempt_logs[0]
    assert attempt_log.attempt_number == 1
    assert "Test error" in attempt_log.exception

    assert len(retry_failed_logs) == 1
    failed_log = retry_failed_logs[0]
    assert failed_log.attempt_number == 2
    assert "Test error" in failed_log.exception


def test_retry_max_attempts_env(caplog) -> None:
    os.environ["WEAVE_RETRY_MAX_ATTEMPTS"] = "2"
    caplog.set_level(logging.INFO, logger="weave.utils.retry")

    @with_retry
    def func():
        raise RuntimeError("Test error")

    with pytest.raises(RuntimeError):
        func()

    retry_attempt_logs = [r for r in caplog.records if r.msg == "retry_attempt"]
    retry_failed_logs = [r for r in caplog.records if r.msg == "retry_failed"]

    assert len(retry_attempt_logs) == 1
    attempt_log = retry_attempt_logs[0]
    assert attempt_log.attempt_number == 1
    assert "Test error" in attempt_log.exception

    assert len(retry_failed_logs) == 1
    failed_log = retry_failed_logs[0]
    assert failed_log.attempt_number == 2
    assert "Test error" in failed_log.exception

    del os.environ["WEAVE_RETRY_MAX_ATTEMPTS"]


def test_retry_max_interval_settings(client_creator, caplog, monkeypatch) -> None:
    caplog.set_level(logging.INFO, logger="weave.utils.retry")

    original_wait = tenacity.wait_exponential_jitter
    call_args = []

    def mock_wait_exponential_jitter(initial=0, max=None):
        call_args.append(max)
        return original_wait(initial=initial, max=max)

    monkeypatch.setattr(
        tenacity, "wait_exponential_jitter", mock_wait_exponential_jitter
    )

    @with_retry
    def func():
        raise RuntimeError("Test error")

    custom_max_interval = 30.0
    with client_creator(settings=UserSettings(retry_max_interval=custom_max_interval)):
        with pytest.raises(RuntimeError):
            func()

    assert custom_max_interval in call_args


def test_retry_max_interval_env(caplog, monkeypatch) -> None:
    os.environ["WEAVE_RETRY_MAX_INTERVAL"] = "25.0"
    caplog.set_level(logging.INFO, logger="weave.utils.retry")

    original_wait = tenacity.wait_exponential_jitter
    call_args = []

    def mock_wait_exponential_jitter(initial=0, max=None):
        call_args.append(max)
        return original_wait(initial=initial, max=max)

    monkeypatch.setattr(
        tenacity, "wait_exponential_jitter", mock_wait_exponential_jitter
    )

    @with_retry
    def func():
        raise RuntimeError("Test error")

    with pytest.raises(RuntimeError):
        func()

    assert 25.0 in call_args

    del os.environ["WEAVE_RETRY_MAX_INTERVAL"]
