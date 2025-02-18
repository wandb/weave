import os
import time
import timeit
from unittest import mock

import pytest

import weave
from tests.trace.util import capture_output, flushing_callback
from weave.trace.constants import TRACE_CALL_EMOJI
from weave.trace.settings import UserSettings, parse_and_apply_settings
from weave.trace.weave_client import get_parallelism_settings


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

    assert (
        disabled_time * 10 < enabled_time
    ), "Disabled weave should be faster than enabled weave"


def test_disabled_env(client):
    os.environ["WEAVE_DISABLED"] = "true"
    disabled_time = timeit.timeit(func, number=10)
    calls = list(client.get_calls())
    assert len(calls) == 0

    os.environ["WEAVE_DISABLED"] = "false"
    enabled_time = timeit.timeit(func, number=10)
    calls = list(client.get_calls())
    assert len(calls) == 10

    assert (
        disabled_time * 10 < enabled_time
    ), "Disabled weave should be faster than enabled weave"



def test_disabled_env_client():
    os.environ["WEAVE_DISABLED"] = "true"
    client = weave.init("entity/project")

    # Verify that the client is disabled
    # Would be nicer to have a specific property
    assert client.project == "DISABLED"

    assert func() == 1

    # No error implies that no calls were sent to the server
    # since this would require writing to `entity/project`
    client._flush()

    os.environ["WEAVE_DISABLED"] = "false"


def test_print_call_link_setting(client_creator):
    parse_and_apply_settings(UserSettings(print_call_link=False))
    with client_creator() as client:
        callbacks = [flushing_callback(client)]
        with capture_output(callbacks) as captured:
            func()
    assert TRACE_CALL_EMOJI not in captured.getvalue()

    parse_and_apply_settings(UserSettings(print_call_link=True))
    with client_creator() as client:
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
    time.sleep(1)


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

    parse_and_apply_settings(UserSettings(client_parallelism=0))
    with mock.patch("os.cpu_count", return_value=4):
        with client_creator() as client:
            assert client.future_executor._max_workers == 0
            assert client.future_executor._executor == None
            wait_time_0, queue_time_0 = speed_test(client)

    parse_and_apply_settings(UserSettings(client_parallelism=1))
    with mock.patch("os.cpu_count", return_value=4):
        with client_creator() as client:
            assert client.future_executor._max_workers == 1
            assert client.future_executor._executor._max_workers == 1
            wait_time_1, queue_time_1 = speed_test(client)

    # Assert that the queue time is much less for 1 than 0
    assert queue_time_0 > queue_time_1
    # Assert that the total time is about the same
    assert wait_time_0 + queue_time_0 == pytest.approx(
        wait_time_1 + queue_time_1, abs=0.1
    )

    parse_and_apply_settings(UserSettings(client_parallelism=10))
    with client_creator() as client:
        assert client.future_executor._max_workers == 5
        assert client.future_executor._executor._max_workers == 5
        assert client.future_executor_fastlane._max_workers == 5
        wait_time_10, queue_time_10 = speed_test(client)

    # Assert that the queue time is about the same for 10 and 1
    assert queue_time_1 == pytest.approx(queue_time_10, abs=0.1)
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
